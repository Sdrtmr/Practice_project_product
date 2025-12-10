# app.py
import sqlite3
from datetime import datetime
import base64
import csv
from pathlib import Path
import json
from flask import Flask, render_template, request, jsonify, send_file
import io
import os
import random

# ========== Flask приложение ==========
app = Flask(__name__)

# ========== База данных SQLite ==========
def init_db():
    # Подключаемся к существующей базе данных из файла или создаем новую
    conn = sqlite3.connect('furniture_production.db')
    cursor = conn.cursor()
    
    # Удаляем старые таблицы, если они есть (для тестирования)
    cursor.execute("DROP TABLE IF EXISTS aggregated_products")
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS products")
    
    # Создаем таблицы
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        article INTEGER NOT NULL,
        product_type TEXT NOT NULL,
        product_type_coefficient REAL,
        minimum_partner_price REAL,
        main_material TEXT,
        raw_material_loss_percentage REAL,
        workshop_name TEXT,
        workshop_type TEXT,
        number_of_people_for_production INTEGER,
        manufacturing_time_hours REAL,
        total_labor_hours REAL
    )
    ''')
    
    # Таблица для агрегированных данных по продуктам
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS aggregated_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article INTEGER UNIQUE NOT NULL,
        product_name TEXT NOT NULL,
        product_type TEXT NOT NULL,
        product_type_coefficient REAL,
        minimum_partner_price REAL,
        main_material TEXT,
        raw_material_loss_percentage REAL,
        total_production_hours REAL,
        avg_manufacturing_time REAL,
        workshop_count INTEGER
    )
    ''')
    
    # Таблица заказов (расширенная)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT,
        delivery_address TEXT,
        order_notes TEXT,
        urgency TEXT DEFAULT 'обычный',
        payment_method TEXT DEFAULT 'наличные',
        quantity INTEGER NOT NULL,
        unit_price REAL,
        total_price REAL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivery_date DATE,
        status TEXT DEFAULT 'новый'
    )
    ''')
    
    # Загружаем данные из CSV файла
    load_data_from_csv(conn, cursor)
    
    # Создаем агрегированные данные
    create_aggregated_data(conn, cursor)
    
    conn.commit()
    conn.close()

def load_data_from_csv(conn, cursor):
    """Загрузка данных из CSV файла в базу данных"""
    try:
        csv_file_path = 'combined_data.csv'
        if not os.path.exists(csv_file_path):
            print(f"Файл {csv_file_path} не найден!")
            return
            
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
            csv_reader = csv.DictReader(file)
            
            # Проверяем заголовки
            print(f"Заголовки CSV: {csv_reader.fieldnames}")
            
            for i, row in enumerate(csv_reader, 1):
                try:
                    # Преобразуем числовые значения
                    article = int(row['article']) if row['article'] and row['article'].isdigit() else 0
                    
                    # Обрабатываем числовые поля
                    product_type_coefficient = float(row['product_type_coefficient']) if row['product_type_coefficient'] else 0.0
                    minimum_partner_price = float(row['minimum_partner_price']) if row['minimum_partner_price'] else 0.0
                    raw_material_loss_percentage = float(row['raw_material_loss_percentage']) if row['raw_material_loss_percentage'] else 0.0
                    number_of_people = int(row['number_of_people_for_production']) if row['number_of_people_for_production'] else 0
                    manufacturing_time = float(row['manufacturing_time_hours']) if row['manufacturing_time_hours'] else 0.0
                    total_labor = float(row['total_labor_hours']) if row['total_labor_hours'] else 0.0
                    
                    cursor.execute('''
                    INSERT INTO products (
                        id, product_name, article, product_type, product_type_coefficient,
                        minimum_partner_price, main_material, raw_material_loss_percentage,
                        workshop_name, workshop_type, number_of_people_for_production,
                        manufacturing_time_hours, total_labor_hours
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        int(row['id']),
                        row['product_name'],
                        article,
                        row['product_type'],
                        product_type_coefficient,
                        minimum_partner_price,
                        row['main_material'],
                        raw_material_loss_percentage,
                        row['workshop_name'],
                        row['workshop_type'],
                        number_of_people,
                        manufacturing_time,
                        total_labor
                    ))
                    
                    if i % 20 == 0:
                        print(f"Загружено {i} записей...")
                        
                except Exception as e:
                    print(f"Ошибка при обработке строки {i}: {e}")
                    print(f"Данные строки: {row}")
                    
        print(f"Всего загружено {i} записей из CSV файла")
        
    except Exception as e:
        print(f"Ошибка при загрузке данных из CSV: {e}")

def create_aggregated_data(conn, cursor):
    """Создание агрегированных данных по продуктам"""
    try:
        print("Создание агрегированных данных...")
        
        # Сначала очистим таблицу
        cursor.execute("DELETE FROM aggregated_products")
        
        # Используем правильные имена столбцов
        cursor.execute('''
        INSERT INTO aggregated_products (
            article, product_name, product_type, product_type_coefficient,
            minimum_partner_price, main_material, raw_material_loss_percentage,
            total_production_hours, avg_manufacturing_time, workshop_count
        )
        SELECT 
            article,
            product_name,
            product_type,
            AVG(product_type_coefficient) as avg_coefficient,
            MIN(minimum_partner_price) as min_price,
            main_material,
            AVG(raw_material_loss_percentage) as avg_loss,
            SUM(total_labor_hours) as total_hours,
            AVG(manufacturing_time_hours) as avg_time,
            COUNT(*) as workshop_count
        FROM products
        GROUP BY article, product_name, product_type, main_material
        ORDER BY product_name
        ''')
        
        print("Агрегированные данные успешно созданы")
        
        # Проверяем сколько записей создано
        cursor.execute("SELECT COUNT(*) FROM aggregated_products")
        count = cursor.fetchone()[0]
        print(f"Создано {count} агрегированных записей")
        
    except Exception as e:
        print(f"Ошибка при создании агрегированных данных: {e}")

# Инициализация БД
init_db()

# Функция для создания логотипа из PNG файла
def create_logo():
    try:
        # Пробуем прочитать файл logo.png
        with open('logo.png', 'rb') as f:
            logo_data = f.read()
            logo_base64 = base64.b64encode(logo_data).decode('utf-8')
            return "data:image/png;base64," + logo_base64
    except FileNotFoundError:
        # Если файл не найден, создаем красивый SVG логотип
        print("Файл logo.png не найден, используется SVG логотип")
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="60" viewBox="0 0 200 60" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
        </linearGradient>
        <linearGradient id="grad2" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#f093fb;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#f5576c;stop-opacity:1" />
        </linearGradient>
    </defs>
    <rect width="200" height="60" rx="12" fill="url(#grad1)"/>
    <rect x="15" y="10" width="40" height="40" rx="8" fill="url(#grad2)"/>
    <path d="M25,25 L45,25 M25,30 L45,30 M25,35 L45,35" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <text x="65" y="28" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="white">FURNITURE</text>
    <text x="65" y="42" font-family="Arial, sans-serif" font-size="12" fill="rgba(255,255,255,0.8)">PRODUCTION</text>
</svg>'''
        
        logo_base64 = "data:image/svg+xml;base64," + base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        return logo_base64

logo_base64 = create_logo()

# ========== HTML страница с полным визуальным обновлением ==========
html_content = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Furniture Pro - Управление производством</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Light Theme Variables */
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --accent-color: #4f46e5;
            --accent-hover: #4338ca;
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --bg-card: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            --border-color: #e2e8f0;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.04);
            --shadow-lg: 0 10px 25px -5px rgba(0,0,0,0.08), 0 10px 10px -5px rgba(0,0,0,0.02);
            --shadow-xl: 0 20px 40px -15px rgba(0,0,0,0.1);
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --info-color: #3b82f6;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
        }
        
        .dark-theme {
            /* Dark Theme Variables */
            --primary-gradient: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
            --secondary-gradient: linear-gradient(135deg, #f472b6 0%, #db2777 100%);
            --accent-color: #8b5cf6;
            --accent-hover: #7c3aed;
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.2);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.25), 0 2px 4px -1px rgba(0,0,0,0.15);
            --shadow-lg: 0 10px 25px -5px rgba(0,0,0,0.25), 0 10px 10px -5px rgba(0,0,0,0.1);
            --shadow-xl: 0 20px 40px -15px rgba(0,0,0,0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            transition: background-color 0.3s, border-color 0.3s, transform 0.2s, box-shadow 0.2s;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--accent-color);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--accent-hover);
        }
        
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header Styles */
        .header {
            background: var(--primary-gradient);
            border-radius: var(--radius-lg);
            padding: 25px 35px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            box-shadow: var(--shadow-lg);
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200px;
            height: 200px;
            background: var(--secondary-gradient);
            border-radius: 50%;
            opacity: 0.2;
            z-index: 0;
        }
        
        .logo-container {
            display: flex;
            align-items: center;
            gap: 20px;
            position: relative;
            z-index: 1;
        }
        
        .logo {
            height: 65px;
            width: 65px;
            object-fit: contain;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
        }
        
        .title-container {
            display: flex;
            flex-direction: column;
        }
        
        .main-title {
            color: white;
            font-size: 28px;
            font-weight: 700;
            font-family: 'Poppins', sans-serif;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .subtitle {
            color: rgba(255, 255, 255, 0.9);
            font-size: 14px;
            font-weight: 400;
        }
        
        /* Theme and User Controls */
        .header-controls {
            display: flex;
            align-items: center;
            gap: 20px;
            position: relative;
            z-index: 1;
        }
        
        .theme-switcher {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            padding: 12px 20px;
            border-radius: var(--radius-xl);
            cursor: pointer;
            user-select: none;
            transition: all 0.3s;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .theme-switcher:hover {
            background: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
        }
        
        .theme-icon {
            font-size: 20px;
            color: white;
        }
        
        .theme-text {
            color: white;
            font-weight: 500;
            font-size: 14px;
        }
        
        .user-profile {
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            padding: 10px 18px;
            border-radius: var(--radius-xl);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .user-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: var(--secondary-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 16px;
        }
        
        .user-info {
            display: flex;
            flex-direction: column;
        }
        
        .user-name {
            color: white;
            font-size: 14px;
            font-weight: 600;
        }
        
        .user-role {
            color: rgba(255, 255, 255, 0.8);
            font-size: 12px;
        }
        
        /* Navigation Cards */
        .nav-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }
        
        .nav-card {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: 30px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .nav-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-xl);
            border-color: var(--accent-color);
        }
        
        .nav-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 6px;
            height: 100%;
            background: var(--primary-gradient);
            border-radius: var(--radius-lg) 0 0 var(--radius-lg);
        }
        
        .nav-card-icon {
            font-size: 36px;
            margin-bottom: 20px;
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .nav-card-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--text-primary);
        }
        
        .nav-card-desc {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 20px;
            line-height: 1.5;
        }
        
        .nav-card-arrow {
            align-self: flex-end;
            color: var(--accent-color);
            font-size: 20px;
            opacity: 0;
            transform: translateX(-10px);
            transition: all 0.3s;
        }
        
        .nav-card:hover .nav-card-arrow {
            opacity: 1;
            transform: translateX(0);
        }
        
        /* Content Sections */
        .content-section {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: 35px;
            margin-bottom: 30px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
            display: none;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .content-section.active {
            display: block;
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .section-title {
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .section-title-icon {
            background: var(--primary-gradient);
            width: 40px;
            height: 40px;
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }
        
        .section-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .action-btn {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            border-radius: var(--radius-md);
            border: none;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .primary-btn {
            background: var(--primary-gradient);
            color: white;
        }
        
        .primary-btn:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        
        .secondary-btn {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .secondary-btn:hover {
            background: var(--accent-color);
            color: white;
            border-color: var(--accent-color);
        }
        
        /* Tables */
        .table-container {
            overflow-x: auto;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-sm);
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        
        .data-table thead {
            background: var(--bg-secondary);
        }
        
        .data-table th {
            padding: 18px 20px;
            text-align: left;
            font-weight: 600;
            color: var(--text-primary);
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }
        
        .data-table td {
            padding: 18px 20px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }
        
        .data-table tbody tr {
            transition: background-color 0.2s;
        }
        
        .data-table tbody tr:hover {
            background-color: var(--bg-secondary);
        }
        
        .data-table tbody tr:last-child td {
            border-bottom: none;
        }
        
        /* Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            gap: 6px;
        }
        
        .badge-new {
            background: linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%);
            color: #1e40af;
        }
        
        .badge-processing {
            background: linear-gradient(135deg, #fef3c7 0%, #fcd34d 100%);
            color: #92400e;
        }
        
        .badge-completed {
            background: linear-gradient(135deg, #d1fae5 0%, #6ee7b7 100%);
            color: #065f46;
        }
        
        .badge-urgent {
            background: linear-gradient(135deg, #fee2e2 0%, #fca5a5 100%);
            color: #991b1b;
        }
        
        .badge-normal {
            background: linear-gradient(135deg, #e0e7ff 0%, #a5b4fc 100%);
            color: #3730a3;
        }
        
        /* Product Cards */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
        }
        
        .product-card {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-color);
            overflow: hidden;
            transition: all 0.3s;
            box-shadow: var(--shadow-md);
        }
        
        .product-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-xl);
            border-color: var(--accent-color);
        }
        
        .product-image {
            height: 180px;
            background: var(--primary-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 60px;
        }
        
        .product-content {
            padding: 25px;
        }
        
        .product-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        
        .product-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .product-price {
            font-size: 22px;
            font-weight: 700;
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .product-details {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        
        .detail-item {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        
        .detail-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .detail-value {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
        }
        
        /* Form Styles */
        .form-container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .form-section {
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            padding: 30px;
            margin-bottom: 25px;
            border: 1px solid var(--border-color);
        }
        
        .form-section-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .form-section-icon {
            width: 50px;
            height: 50px;
            border-radius: var(--radius-md);
            background: var(--primary-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
        }
        
        .form-section-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 14px;
        }
        
        .form-label.required::after {
            content: ' *';
            color: var(--danger-color);
        }
        
        .form-input, .form-select, .form-textarea {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid var(--border-color);
            border-radius: var(--radius-md);
            background: var(--bg-card);
            color: var(--text-primary);
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            transition: all 0.3s;
        }
        
        .form-input:focus, .form-select:focus, .form-textarea:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        
        .form-textarea {
            min-height: 120px;
            resize: vertical;
        }
        
        .price-summary {
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            padding: 25px;
            margin-top: 30px;
            border: 1px solid var(--border-color);
        }
        
        .price-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
        }
        
        .price-row.total {
            border-bottom: none;
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            margin-top: 10px;
        }
        
        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: 25px;
            border: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 20px;
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
            border-color: var(--accent-color);
        }
        
        .stat-icon {
            width: 60px;
            height: 60px;
            border-radius: var(--radius-lg);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
        }
        
        .stat-icon.orders {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .stat-icon.products {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .stat-icon.production {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        .stat-icon.revenue {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        }
        
        .stat-info {
            flex: 1;
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        /* Loading Animation */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            gap: 20px;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid var(--border-color);
            border-top: 4px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Footer */
        .app-footer {
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
        }
        
        .footer-link {
            color: var(--text-secondary);
            text-decoration: none;
            transition: color 0.3s;
        }
        
        .footer-link:hover {
            color: var(--accent-color);
        }
        
        /* Responsive Design */
        @media (max-width: 1024px) {
            .nav-cards {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }
            
            .header {
                padding: 20px;
                flex-direction: column;
                gap: 20px;
                text-align: center;
            }
            
            .logo-container {
                flex-direction: column;
                text-align: center;
            }
            
            .header-controls {
                width: 100%;
                justify-content: center;
            }
            
            .nav-cards {
                grid-template-columns: 1fr;
            }
            
            .section-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .section-actions {
                width: 100%;
                justify-content: flex-start;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .products-grid {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .product-details {
                grid-template-columns: 1fr;
            }
            
            .user-profile {
                padding: 8px 12px;
            }
            
            .user-info {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo-container">
                <img src="''' + logo_base64 + '''" alt="Логотип Furniture Pro" class="logo">
                <div class="title-container">
                    <h1 class="main-title">Furniture Pro</h1>
                    <p class="subtitle">Система управления мебельным производством</p>
                </div>
            </div>
            
            <div class="header-controls">
                <div class="theme-switcher" onclick="toggleTheme()">
                    <span class="theme-icon" id="theme-icon">🌙</span>
                    <span class="theme-text" id="theme-text">Ночной режим</span>
                </div>
                
                <div class="user-profile">
                    <div class="user-avatar">MP</div>
                    <div class="user-info">
                        <div class="user-name">Менеджер Производства</div>
                        <div class="user-role">Администратор</div>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Navigation Cards -->
        <div class="nav-cards">
            <div class="nav-card" onclick="showSection('products')">
                <div class="nav-card-icon">📦</div>
                <h3 class="nav-card-title">Каталог товаров</h3>
                <p class="nav-card-desc">Просмотр всех доступных товаров, их характеристик и цен</p>
                <div class="nav-card-arrow">→</div>
            </div>
            
            <div class="nav-card" onclick="showSection('create-order')">
                <div class="nav-card-icon">➕</div>
                <h3 class="nav-card-title">Новый заказ</h3>
                <p class="nav-card-desc">Создание заказа с детальной информацией о клиенте и доставке</p>
                <div class="nav-card-arrow">→</div>
            </div>
            
            <div class="nav-card" onclick="showSection('orders')">
                <div class="nav-card-icon">📋</div>
                <h3 class="nav-card-title">Заказы</h3>
                <p class="nav-card-desc">История всех заказов, статусы и управление ими</p>
                <div class="nav-card-arrow">→</div>
            </div>
            
            <div class="nav-card" onclick="showSection('production')">
                <div class="nav-card-icon">🏭</div>
                <h3 class="nav-card-title">Производство</h3>
                <p class="nav-card-desc">Данные о производственных процессах и цехах</p>
                <div class="nav-card-arrow">→</div>
            </div>
        </div>
        
        <!-- Stats Overview -->
        <div class="stats-grid" id="stats-overview">
            <div class="stat-card">
                <div class="stat-icon orders">📊</div>
                <div class="stat-info">
                    <div class="stat-value" id="total-orders">0</div>
                    <div class="stat-label">Всего заказов</div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon products">📦</div>
                <div class="stat-info">
                    <div class="stat-value" id="total-products">0</div>
                    <div class="stat-label">Товаров в каталоге</div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon production">⚙️</div>
                <div class="stat-info">
                    <div class="stat-value" id="total-workshops">0</div>
                    <div class="stat-label">Производственных цехов</div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon revenue">💰</div>
                <div class="stat-info">
                    <div class="stat-value" id="total-revenue">0</div>
                    <div class="stat-label">Общая выручка</div>
                </div>
            </div>
        </div>
        
        <!-- Products Section -->
        <section id="products" class="content-section active">
            <div class="section-header">
                <div class="section-title">
                    <div class="section-title-icon">📦</div>
                    <h2>Каталог товаров</h2>
                </div>
                <div class="section-actions">
                    <button class="action-btn secondary-btn" onclick="loadRandomProducts()">
                        <i class="fas fa-sync-alt"></i>
                        Обновить
                    </button>
                    <button class="action-btn primary-btn" onclick="exportProducts()">
                        <i class="fas fa-download"></i>
                        Экспорт
                    </button>
                </div>
            </div>
            
            <div class="table-container">
                <table class="data-table" id="products-table">
                    <thead>
                        <tr>
                            <th>Артикул</th>
                            <th>Название товара</th>
                            <th>Тип</th>
                            <th>Материал</th>
                            <th>Цена</th>
                            <th>Время производства</th>
                            <th>Цехов</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody id="products-table-body">
                        <tr>
                            <td colspan="8" class="loading">
                                <div class="spinner"></div>
                                <p>Загрузка данных...</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>
        
        <!-- Create Order Section -->
        <section id="create-order" class="content-section">
            <div class="section-header">
                <div class="section-title">
                    <div class="section-title-icon">➕</div>
                    <h2>Создание нового заказа</h2>
                </div>
            </div>
            
            <form id="orderForm" onsubmit="createOrder(event)" class="form-container">
                <!-- Product Selection -->
                <div class="form-section">
                    <div class="form-section-header">
                        <div class="form-section-icon">📦</div>
                        <h3>Выбор товара</h3>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label required">Товар</label>
                        <select id="productSelect" class="form-select" required onchange="updateProductInfo()">
                            <option value="">Выберите товар из списка</option>
                        </select>
                    </div>
                    
                    <div id="product-info-container" style="display: none;">
                        <div class="form-grid">
                            <div class="form-group">
                                <label class="form-label">Название</label>
                                <input type="text" id="product-name" class="form-input" readonly>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Тип</label>
                                <input type="text" id="product-type" class="form-input" readonly>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Материал</label>
                                <input type="text" id="product-material" class="form-input" readonly>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Цена за единицу</label>
                                <input type="text" id="product-price" class="form-input" readonly>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label required">Количество</label>
                        <input type="number" id="quantity" class="form-input" min="1" value="1" required onchange="updatePrice()">
                    </div>
                </div>
                
                <!-- Customer Information -->
                <div class="form-section">
                    <div class="form-section-header">
                        <div class="form-section-icon">👤</div>
                        <h3>Информация о клиенте</h3>
                    </div>
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label class="form-label required">Имя клиента</label>
                            <input type="text" id="customerName" class="form-input" required placeholder="Введите полное имя">
                        </div>
                        <div class="form-group">
                            <label class="form-label required">Телефон</label>
                            <input type="tel" id="customerPhone" class="form-input" required placeholder="+7 (999) 123-45-67">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Email</label>
                            <input type="email" id="customerEmail" class="form-input" placeholder="client@example.com">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Адрес доставки</label>
                            <input type="text" id="deliveryAddress" class="form-input" placeholder="Город, улица, дом, квартира">
                        </div>
                    </div>
                </div>
                
                <!-- Order Details -->
                <div class="form-section">
                    <div class="form-section-header">
                        <div class="form-section-icon">⚙️</div>
                        <h3>Детали заказа</h3>
                    </div>
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label class="form-label">Срочность</label>
                            <select id="urgency" class="form-select">
                                <option value="обычный">Обычный (7-10 дней)</option>
                                <option value="срочный">Срочный (3-5 дней)</option>
                                <option value="очень срочно">Очень срочно (1-2 дня)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Способ оплаты</label>
                            <select id="paymentMethod" class="form-select">
                                <option value="наличные">Наличные при получении</option>
                                <option value="карта">Банковская карта</option>
                                <option value="перевод">Банковский перевод</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Желаемая дата доставки</label>
                            <input type="date" id="deliveryDate" class="form-input">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Примечания к заказу</label>
                        <textarea id="orderNotes" class="form-textarea" placeholder="Особые требования, пожелания, комментарии..."></textarea>
                    </div>
                </div>
                
                <!-- Price Summary -->
                <div class="price-summary">
                    <h3 style="margin-bottom: 20px; color: var(--text-primary);">Сводка по стоимости</h3>
                    <div class="price-row">
                        <span>Цена за единицу:</span>
                        <span id="unit-price-display">0.00 ₽</span>
                    </div>
                    <div class="price-row">
                        <span>Количество:</span>
                        <span id="quantity-display">1</span>
                    </div>
                    <div class="price-row total">
                        <span>Итого к оплате:</span>
                        <span id="total-price-display" style="background: var(--primary-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">0.00 ₽</span>
                    </div>
                </div>
                
                <button type="submit" class="action-btn primary-btn" style="width: 100%; padding: 18px; font-size: 16px; margin-top: 30px;">
                    <i class="fas fa-check-circle"></i>
                    Создать заказ
                </button>
            </form>
        </section>
        
        <!-- Orders Section -->
        <section id="orders" class="content-section">
            <div class="section-header">
                <div class="section-title">
                    <div class="section-title-icon">📋</div>
                    <h2>История заказов</h2>
                </div>
                <div class="section-actions">
                    <button class="action-btn secondary-btn" onclick="loadOrders()">
                        <i class="fas fa-sync-alt"></i>
                        Обновить
                    </button>
                </div>
            </div>
            
            <div class="table-container">
                <table class="data-table" id="orders-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Товар</th>
                            <th>Клиент</th>
                            <th>Телефон</th>
                            <th>Кол-во</th>
                            <th>Сумма</th>
                            <th>Статус</th>
                            <th>Срочность</th>
                            <th>Дата заказа</th>
                        </tr>
                    </thead>
                    <tbody id="orders-table-body">
                        <tr>
                            <td colspan="9" class="loading">
                                <div class="spinner"></div>
                                <p>Загрузка заказов...</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>
        
        <!-- Production Section -->
        <section id="production" class="content-section">
            <div class="section-header">
                <div class="section-title">
                    <div class="section-title-icon">🏭</div>
                    <h2>Производственные данные</h2>
                </div>
                <div class="section-actions">
                    <button class="action-btn secondary-btn" onclick="loadProductionData()">
                        <i class="fas fa-sync-alt"></i>
                        Обновить
                    </button>
                </div>
            </div>
            
            <div class="table-container">
                <table class="data-table" id="production-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Товар</th>
                            <th>Цех</th>
                            <th>Тип цеха</th>
                            <th>Рабочих</th>
                            <th>Время (ч)</th>
                            <th>Трудозатраты (ч)</th>
                        </tr>
                    </thead>
                    <tbody id="production-table-body">
                        <tr>
                            <td colspan="7" class="loading">
                                <div class="spinner"></div>
                                <p>Загрузка производственных данных...</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>
        
        <!-- Footer -->
        <footer class="app-footer">
            <div class="footer-links">
                <a href="#" class="footer-link" onclick="showSection('products')">Товары</a>
                <a href="#" class="footer-link" onclick="showSection('orders')">Заказы</a>
                <a href="#" class="footer-link" onclick="showSection('production')">Производство</a>
                <a href="#" class="footer-link">Помощь</a>
                <a href="#" class="footer-link">Контакты</a>
            </div>
            <p>© 2024 Furniture Pro Production System. Все права защищены.</p>
            <p style="margin-top: 10px; font-size: 12px; color: var(--text-muted);">Версия 2.0.1</p>
        </footer>
    </div>

    <script>
        // Theme Management
        function toggleTheme() {
            const body = document.body;
            const themeIcon = document.getElementById('theme-icon');
            const themeText = document.getElementById('theme-text');
            
            if (body.classList.contains('dark-theme')) {
                body.classList.remove('dark-theme');
                themeIcon.textContent = '🌙';
                themeText.textContent = 'Ночной режим';
                localStorage.setItem('theme', 'light');
            } else {
                body.classList.add('dark-theme');
                themeIcon.textContent = '☀️';
                themeText.textContent = 'Дневной режим';
                localStorage.setItem('theme', 'dark');
            }
        }
        
        // Load theme from localStorage
        function loadTheme() {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-theme');
                document.getElementById('theme-icon').textContent = '☀️';
                document.getElementById('theme-text').textContent = 'Дневной режим';
            }
        }
        
        let selectedProduct = null;
        
        // Show/Hide Sections
        function showSection(sectionId) {
            document.querySelectorAll('.content-section').forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(sectionId).classList.add('active');
            
            // Load data for the active section
            if (sectionId === 'products') {
                loadProducts();
                updateStats();
            }
            if (sectionId === 'orders') loadOrders();
            if (sectionId === 'production') loadProductionData();
        }
        
        // Update Stats Overview
        async function updateStats() {
            try {
                // Load orders count
                const ordersResponse = await fetch('/api/orders');
                const orders = await ordersResponse.json();
                document.getElementById('total-orders').textContent = orders.length;
                
                // Load products count
                const productsResponse = await fetch('/api/products');
                const products = await productsResponse.json();
                document.getElementById('total-products').textContent = products.length;
                
                // Calculate total revenue
                let totalRevenue = 0;
                orders.forEach(order => {
                    if (order.total_price) {
                        totalRevenue += order.total_price;
                    }
                });
                document.getElementById('total-revenue').textContent = totalRevenue.toLocaleString('ru-RU', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0
                }) + ' ₽';
                
                // Load production data for workshop count
                const productionResponse = await fetch('/api/production');
                const productionData = await productionResponse.json();
                const uniqueWorkshops = [...new Set(productionData.map(item => item.workshop_name))];
                document.getElementById('total-workshops').textContent = uniqueWorkshops.length;
                
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }
        
        // Load Products with improved UI
        async function loadProducts() {
            const tableBody = document.getElementById('products-table-body');
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="loading">
                        <div class="spinner"></div>
                        <p>Загрузка товаров...</p>
                    </td>
                </tr>
            `;
            
            try {
                const response = await fetch('/api/random_products');
                const products = await response.json();
                
                if (products.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                <i class="fas fa-box-open" style="font-size: 48px; margin-bottom: 20px; opacity: 0.5;"></i>
                                <p>Товары не найдены</p>
                            </td>
                        </tr>
                    `;
                    return;
                }
                
                let html = '';
                products.forEach(product => {
                    const price = product.minimum_partner_price || 0;
                    const hours = product.total_production_hours || 0;
                    const workshops = product.workshop_count || 1;
                    
                    html += `
                        <tr>
                            <td><strong>${product.article}</strong></td>
                            <td>
                                <div style="font-weight: 600; color: var(--text-primary);">${product.product_name}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">${product.product_type}</div>
                            </td>
                            <td>${product.product_type}</td>
                            <td>${product.main_material || '—'}</td>
                            <td style="font-weight: 700; color: var(--accent-color);">
                                ${price.toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})} ₽
                            </td>
                            <td>${hours.toFixed(1)} ч</td>
                            <td>
                                <span class="badge badge-normal">${workshops} цех${workshops > 1 ? 'а' : ''}</span>
                            </td>
                            <td>
                                <button class="secondary-btn" style="padding: 8px 16px; font-size: 12px;" 
                                        onclick="selectProductForOrder(${product.article})">
                                    <i class="fas fa-cart-plus"></i> Заказать
                                </button>
                            </td>
                        </tr>
                    `;
                });
                
                tableBody.innerHTML = html;
                
            } catch (error) {
                console.error('Error loading products:', error);
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="8" style="text-align: center; padding: 40px; color: var(--danger-color);">
                            <i class="fas fa-exclamation-triangle" style="font-size: 48px; margin-bottom: 20px;"></i>
                            <p>Ошибка загрузки данных</p>
                            <button class="secondary-btn" onclick="loadProducts()" style="margin-top: 20px;">
                                <i class="fas fa-redo"></i> Попробовать снова
                            </button>
                        </td>
                    </tr>
                `;
            }
        }
        
        // Load all products for dropdown
        async function loadAllProductsForDropdown() {
            try {
                const response = await fetch('/api/products');
                const products = await response.json();
                
                const select = document.getElementById('productSelect');
                select.innerHTML = '<option value="">Выберите товар из списка</option>';
                
                products.forEach(product => {
                    const option = document.createElement('option');
                    option.value = product.article;
                    option.setAttribute('data-price', product.minimum_partner_price || 0);
                    option.setAttribute('data-name', product.product_name);
                    option.setAttribute('data-type', product.product_type);
                    option.setAttribute('data-material', product.main_material || 'Не указан');
                    option.textContent = `${product.product_name} - ${(product.minimum_partner_price || 0).toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})} ₽`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Error loading products for dropdown:', error);
            }
        }
        
        // Update product info when selected
        function updateProductInfo() {
            const select = document.getElementById('productSelect');
            const selectedOption = select.options[select.selectedIndex];
            const container = document.getElementById('product-info-container');
            
            if (selectedOption.value) {
                const price = parseFloat(selectedOption.getAttribute('data-price')) || 0;
                const name = selectedOption.getAttribute('data-name');
                const type = selectedOption.getAttribute('data-type');
                const material = selectedOption.getAttribute('data-material');
                
                selectedProduct = {
                    article: selectedOption.value,
                    price: price,
                    name: name,
                    type: type,
                    material: material
                };
                
                // Update form fields
                document.getElementById('product-name').value = name;
                document.getElementById('product-type').value = type;
                document.getElementById('product-material').value = material;
                document.getElementById('product-price').value = price.toLocaleString('ru-RU', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }) + ' ₽';
                
                container.style.display = 'block';
                updatePrice();
            } else {
                selectedProduct = null;
                container.style.display = 'none';
                updatePrice();
            }
        }
        
        // Select product for order from products table
        function selectProductForOrder(article) {
            showSection('create-order');
            
            // Find and select the product in dropdown
            const select = document.getElementById('productSelect');
            for (let i = 0; i < select.options.length; i++) {
                if (parseInt(select.options[i].value) === article) {
                    select.selectedIndex = i;
                    updateProductInfo();
                    break;
                }
            }
            
            // Scroll to form
            document.getElementById('create-order').scrollIntoView({ behavior: 'smooth' });
        }
        
        // Update price calculation
        function updatePrice() {
            const quantity = parseInt(document.getElementById('quantity').value) || 1;
            document.getElementById('quantity-display').textContent = quantity;
            
            if (selectedProduct && selectedProduct.price) {
                const unitPrice = selectedProduct.price;
                const totalPrice = unitPrice * quantity;
                
                document.getElementById('unit-price-display').textContent = 
                    unitPrice.toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' ₽';
                document.getElementById('total-price-display').textContent = 
                    totalPrice.toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' ₽';
            } else {
                document.getElementById('unit-price-display').textContent = '0.00 ₽';
                document.getElementById('total-price-display').textContent = '0.00 ₽';
            }
        }
        
        // Load production data
        async function loadProductionData() {
            const tableBody = document.getElementById('production-table-body');
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="loading">
                        <div class="spinner"></div>
                        <p>Загрузка данных...</p>
                    </td>
                </tr>
            `;
            
            try {
                const response = await fetch('/api/production');
                const productionData = await response.json();
                
                if (productionData.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                <i class="fas fa-industry" style="font-size: 48px; margin-bottom: 20px; opacity: 0.5;"></i>
                                <p>Производственные данные отсутствуют</p>
                            </td>
                        </tr>
                    `;
                    return;
                }
                
                let html = '';
                productionData.slice(0, 50).forEach(item => {
                    html += `
                        <tr>
                            <td>${item.id}</td>
                            <td>
                                <div style="font-weight: 600; color: var(--text-primary);">${item.product_name}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">Арт. ${item.article}</div>
                            </td>
                            <td>${item.workshop_name}</td>
                            <td>
                                <span class="badge ${item.workshop_type === 'основной' ? 'badge-normal' : 'badge-processing'}">
                                    ${item.workshop_type}
                                </span>
                            </td>
                            <td>${item.number_of_people_for_production}</td>
                            <td>${item.manufacturing_time_hours}</td>
                            <td>
                                <span style="font-weight: 600; color: var(--accent-color);">
                                    ${item.total_labor_hours}
                                </span>
                            </td>
                        </tr>
                    `;
                });
                
                tableBody.innerHTML = html;
                
            } catch (error) {
                console.error('Error loading production data:', error);
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 40px; color: var(--danger-color);">
                            <i class="fas fa-exclamation-triangle" style="font-size: 48px; margin-bottom: 20px;"></i>
                            <p>Ошибка загрузки данных</p>
                        </td>
                    </tr>
                `;
            }
        }
        
        // Load orders
        async function loadOrders() {
            const tableBody = document.getElementById('orders-table-body');
            tableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="loading">
                        <div class="spinner"></div>
                        <p>Загрузка заказов...</p>
                    </td>
                </tr>
            `;
            
            try {
                const response = await fetch('/api/orders');
                const orders = await response.json();
                
                if (orders.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="9" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                <i class="fas fa-clipboard-list" style="font-size: 48px; margin-bottom: 20px; opacity: 0.5;"></i>
                                <p>Заказы отсутствуют</p>
                            </td>
                        </tr>
                    `;
                    return;
                }
                
                let html = '';
                orders.forEach(order => {
                    const date = new Date(order.order_date);
                    const formattedDate = date.toLocaleDateString('ru-RU');
                    const formattedTime = date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
                    
                    const statusBadge = order.status === 'новый' ? 'badge-new' : 
                                      order.status === 'в обработке' ? 'badge-processing' : 'badge-completed';
                    
                    const urgencyBadge = order.urgency === 'очень срочно' ? 'badge-urgent' : 
                                       order.urgency === 'срочный' ? 'badge-processing' : 'badge-normal';
                    
                    html += `
                        <tr>
                            <td><strong>#${order.id}</strong></td>
                            <td>
                                <div style="font-weight: 600; color: var(--text-primary);">${order.product_name}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">${order.quantity} шт.</div>
                            </td>
                            <td>
                                <div>${order.customer_name}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">${order.customer_email || ''}</div>
                            </td>
                            <td>${order.customer_phone}</td>
                            <td>${order.quantity}</td>
                            <td style="font-weight: 700; color: var(--accent-color);">
                                ${order.total_price ? order.total_price.toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' ₽' : '—'}
                            </td>
                            <td><span class="badge ${statusBadge}">${order.status}</span></td>
                            <td><span class="badge ${urgencyBadge}">${order.urgency || 'обычный'}</span></td>
                            <td>
                                <div>${formattedDate}</div>
                                <div style="font-size: 12px; color: var(--text-muted);">${formattedTime}</div>
                            </td>
                        </tr>
                    `;
                });
                
                tableBody.innerHTML = html;
                
            } catch (error) {
                console.error('Error loading orders:', error);
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; padding: 40px; color: var(--danger-color);">
                            <i class="fas fa-exclamation-triangle" style="font-size: 48px; margin-bottom: 20px;"></i>
                            <p>Ошибка загрузки заказов</p>
                        </td>
                    </tr>
                `;
            }
        }
        
        // Create order
        async function createOrder(event) {
            event.preventDefault();
            
            const productArticle = document.getElementById('productSelect').value;
            const customerName = document.getElementById('customerName').value;
            const customerPhone = document.getElementById('customerPhone').value;
            const customerEmail = document.getElementById('customerEmail').value;
            const deliveryAddress = document.getElementById('deliveryAddress').value;
            const orderNotes = document.getElementById('orderNotes').value;
            const urgency = document.getElementById('urgency').value;
            const paymentMethod = document.getElementById('paymentMethod').value;
            const quantity = parseInt(document.getElementById('quantity').value);
            const deliveryDate = document.getElementById('deliveryDate').value;
            
            // Validation
            if (!productArticle || !customerName || !customerPhone) {
                showNotification('Пожалуйста, заполните обязательные поля', 'error');
                return;
            }
            
            if (quantity < 1) {
                showNotification('Количество должно быть не менее 1', 'error');
                return;
            }
            
            const unitPrice = selectedProduct ? selectedProduct.price : 0;
            const totalPrice = unitPrice * quantity;
            
            const formData = new FormData();
            formData.append('product_article', productArticle);
            formData.append('customer_name', customerName);
            formData.append('customer_phone', customerPhone);
            formData.append('customer_email', customerEmail);
            formData.append('delivery_address', deliveryAddress);
            formData.append('order_notes', orderNotes);
            formData.append('urgency', urgency);
            formData.append('payment_method', paymentMethod);
            formData.append('quantity', quantity);
            formData.append('unit_price', unitPrice);
            formData.append('total_price', totalPrice);
            formData.append('delivery_date', deliveryDate);
            
            try {
                const response = await fetch('/api/create_order', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showNotification(`Заказ №${result.order_id} успешно создан! Сумма: ${totalPrice.toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})} ₽`, 'success');
                    
                    // Reset form
                    document.getElementById('orderForm').reset();
                    document.getElementById('product-info-container').style.display = 'none';
                    selectedProduct = null;
                    updatePrice();
                    
                    // Update stats and show orders section
                    updateStats();
                    setTimeout(() => {
                        showSection('orders');
                        loadOrders();
                    }, 1500);
                    
                } else {
                    showNotification(`Ошибка: ${result.error}`, 'error');
                }
            } catch (error) {
                console.error('Error creating order:', error);
                showNotification('Произошла ошибка при создании заказа', 'error');
            }
        }
        
        // Show notification
        function showNotification(message, type = 'info') {
            // Remove existing notification
            const existingNotification = document.querySelector('.notification');
            if (existingNotification) {
                existingNotification.remove();
            }
            
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.innerHTML = `
                <div style="position: fixed; top: 30px; right: 30px; background: ${type === 'success' ? '#10b981' : '#ef4444'}; 
                     color: white; padding: 15px 25px; border-radius: var(--radius-md); 
                     box-shadow: var(--shadow-lg); z-index: 1000; display: flex; 
                     align-items: center; gap: 12px; animation: slideIn 0.3s ease-out;">
                    <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
                    <span>${message}</span>
                </div>
            `;
            
            document.body.appendChild(notification);
            
            // Remove after 5 seconds
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease-out forwards';
                setTimeout(() => notification.remove(), 300);
            }, 5000);
            
            // Add CSS for animation
            if (!document.querySelector('#notification-styles')) {
                const style = document.createElement('style');
                style.id = 'notification-styles';
                style.textContent = `
                    @keyframes slideIn {
                        from { transform: translateX(100%); opacity: 0; }
                        to { transform: translateX(0); opacity: 1; }
                    }
                    @keyframes slideOut {
                        from { transform: translateX(0); opacity: 1; }
                        to { transform: translateX(100%); opacity: 0; }
                    }
                `;
                document.head.appendChild(style);
            }
        }
        
        // Export products
        function exportProducts() {
            showNotification('Функция экспорта в разработке', 'info');
        }
        
        // Load random products (for backward compatibility)
        async function loadRandomProducts() {
            await loadProducts();
            showNotification('Список товаров обновлен', 'success');
        }
        
        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {
            loadTheme();
            loadAllProductsForDropdown();
            updateStats();
            
            // Add CSS for table row hover effect
            const style = document.createElement('style');
            style.textContent = `
                .data-table tbody tr {
                    transition: all 0.2s;
                }
                .data-table tbody tr:hover {
                    background-color: var(--bg-secondary);
                    transform: translateY(-1px);
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                }
            `;
            document.head.appendChild(style);
        });
    </script>
</body>
</html>
'''

# ========== Маршруты Flask ==========
@app.route('/')
def index():
    return html_content

@app.route('/api/products')
def get_products():
    """Получение всех товаров (для выпадающего списка)"""
    conn = sqlite3.connect('furniture_production.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM aggregated_products ORDER BY product_name")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/random_products')
def get_random_products():
    """Получение случайных товаров (для отображения в таблице)"""
    conn = sqlite3.connect('furniture_production.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Получаем все товары
    cursor.execute("SELECT * FROM aggregated_products")
    all_products = cursor.fetchall()
    
    # Выбираем случайные товары (от 5 до 15 штук)
    if all_products:
        num_products = min(random.randint(5, 15), len(all_products))
        random_products = random.sample(all_products, num_products)
    else:
        random_products = []
    
    conn.close()
    return jsonify([dict(row) for row in random_products])

@app.route('/api/production')
def get_production_data():
    conn = sqlite3.connect('furniture_production.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id LIMIT 50")  # Ограничиваем для производительности
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/orders')
def get_orders():
    conn = sqlite3.connect('furniture_production.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM orders ORDER BY order_date DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/create_order', methods=['POST'])
def create_order_api():
    try:
        product_article = request.form.get('product_article', type=int)
        customer_name = request.form.get('customer_name', '')
        customer_phone = request.form.get('customer_phone', '')
        customer_email = request.form.get('customer_email', '')
        delivery_address = request.form.get('delivery_address', '')
        order_notes = request.form.get('order_notes', '')
        urgency = request.form.get('urgency', 'обычный')
        payment_method = request.form.get('payment_method', 'наличные')
        quantity = request.form.get('quantity', type=int)
        unit_price = request.form.get('unit_price', type=float, default=0.0)
        total_price = request.form.get('total_price', type=float, default=0.0)
        delivery_date = request.form.get('delivery_date', '')
        
        conn = sqlite3.connect('furniture_production.db')
        cursor = conn.cursor()
        
        # Получаем информацию о продукте
        cursor.execute("SELECT product_name FROM aggregated_products WHERE article = ?", (product_article,))
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"error": "Товар не найден"}), 404
        
        product_name = product[0]
        
        cursor.execute('''
            INSERT INTO orders (
                product_id, product_name, customer_name, customer_phone,
                customer_email, delivery_address, order_notes, urgency,
                payment_method, quantity, unit_price, total_price,
                order_date, delivery_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_article, product_name, customer_name, customer_phone,
            customer_email, delivery_address, order_notes, urgency,
            payment_method, quantity, unit_price, total_price,
            datetime.now().isoformat(), delivery_date, 'новый'
        ))
        
        conn.commit()
        order_id = cursor.lastrowid
        conn.close()
        
        return jsonify({"success": True, "order_id": order_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reports')
def get_reports():
    conn = sqlite3.connect('furniture_production.db')
    cursor = conn.cursor()
    
    # Средняя цена по категориям товаров
    cursor.execute("SELECT product_type, AVG(minimum_partner_price) FROM aggregated_products GROUP BY product_type")
    category_data = cursor.fetchall()
    
    # Распределение по основным материалам
    cursor.execute("SELECT main_material, COUNT(*) FROM aggregated_products GROUP BY main_material")
    material_data = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        "category_chart": category_data,
        "material_chart": material_data
    })

if __name__ == "__main__":
    print("="*60)
    print("Furniture Pro - Система управления производством")
    print("Сервер доступен по адресу: http://localhost:5000")
    print("="*60)
    print("🎨 Современный дизайн загружен:")
    print("   • Градиентные фоны и тени")
    print("   • Анимации и плавные переходы")
    print("   • Адаптивный дизайн")
    print("   • Темная/светлая темы")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)