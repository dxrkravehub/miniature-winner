"""
Модуль для работы со схемой трубопровода и визуализации дефектов
"""

from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import math
import os

# Известные объекты инфраструктуры на схеме (координаты в пикселях)
INFRASTRUCTURE_OBJECTS = [
    {'name': 'трубопровод-байпасс', 'x': 678, 'y': 243, 'type': 'bypass'},
    {'name': 'трубопровод-задвижка', 'x': 563, 'y': 349, 'type': 'valve'},
    {'name': 'трубопровод-задвижка', 'x': 393, 'y': 191, 'type': 'valve'},
    {'name': 'трубопровод-задвижка', 'x': 569, 'y': 113, 'type': 'valve'}
]

# Пороги расстояния для классификации (в пикселях)
PROXIMITY_THRESHOLD = 100  # дефект ближе 100 пикселей = "рядом с объектом"

# Цвета для разных классов риска
RISK_COLORS = {
    'High': (255, 0, 0),      # Красный
    'Medium': (255, 165, 0),  # Оранжевый
    'Low': (0, 255, 0)        # Зеленый
}


def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Вычисляет евклидово расстояние между двумя точками"""
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def find_nearest_infrastructure(defect_x: float, defect_y: float) -> Dict:
    """
    Находит ближайший объект инфраструктуры к дефекту
    
    Args:
        defect_x, defect_y: координаты дефекта на схеме (пиксели)
    
    Returns:
        dict с информацией о ближайшем объекте
    """
    min_distance = float('inf')
    nearest_object = None
    
    for obj in INFRASTRUCTURE_OBJECTS:
        distance = calculate_distance(defect_x, defect_y, obj['x'], obj['y'])
        
        if distance < min_distance:
            min_distance = distance
            nearest_object = {
                'name': obj['name'],
                'type': obj['type'],
                'distance': distance,
                'x': obj['x'],
                'y': obj['y']
            }
    
    # Определяем, находится ли дефект "рядом" с объектом
    is_near = min_distance < PROXIMITY_THRESHOLD
    
    return {
        'nearest_object': nearest_object,
        'is_near': is_near,
        'distance': min_distance,
        'classification': nearest_object['name'] if is_near else 'удаленный участок трубопровода'
    }


def assign_scheme_coordinates(defects_df: pd.DataFrame) -> pd.DataFrame:
    """
    Назначает координаты на схеме для дефектов
    
    Использует 'measured_distance_m' для приблизительного расположения
    или случайное распределение если данных нет
    """
    df = defects_df.copy()
    
    # Пока просто случайное распределение
    # TODO: использовать measured_distance_m для более точного позиционирования
    scheme_width = 1200
    scheme_height = 800
    
    df['scheme_x'] = np.random.randint(100, scheme_width - 100, len(df))
    df['scheme_y'] = np.random.randint(100, scheme_height - 100, len(df))
    
    # Находим ближайшую инфраструктуру для каждого дефекта
    locations = []
    for idx, row in df.iterrows():
        location_info = find_nearest_infrastructure(row['scheme_x'], row['scheme_y'])
        locations.append(location_info)
    
    df['infrastructure_location'] = [loc['classification'] for loc in locations]
    df['distance_to_infrastructure'] = [loc['distance'] for loc in locations]
    
    return df


def create_scheme_image(defects_df: pd.DataFrame, 
                       base_scheme_path: str = "scheme.png",
                       output_path: str = "scheme_with_defects.png") -> str:
    """
    Рисует дефекты ПОВЕРХ заранее подготовленной схемы scheme.png
    
    Args:
        defects_df: DataFrame с дефектами (должен содержать scheme_x, scheme_y, risk_class)
        base_scheme_path: путь к базовой схеме (ОБЯЗАТЕЛЕН!)
        output_path: путь для сохранения результата
    
    Returns:
        путь к созданному изображению
    """
    # Проверяем наличие базовой схемы
    if not os.path.exists(base_scheme_path):
        raise FileNotFoundError(
            f"❌ Файл {base_scheme_path} не найден!\n"
            f"Пожалуйста, поместите файл scheme.png в корень проекта.\n"
            f"Это должна быть реальная схема трубопровода."
        )
    
    # Загружаем базовую схему
    img = Image.open(base_scheme_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    
    # Пытаемся загрузить шрифт
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 11)
        font_tiny = ImageFont.truetype("arial.ttf", 9)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_tiny = ImageFont.load_default()
    
    # Рисуем объекты инфраструктуры (если их ещё нет на схеме)
    for obj in INFRASTRUCTURE_OBJECTS:
        x, y = obj['x'], obj['y']
        
        # Рисуем иконку объекта
        if obj['type'] == 'bypass':
            # Байпасс - синий квадрат
            draw.rectangle([x-18, y-18, x+18, y+18], 
                         fill=(0, 100, 255), outline=(255, 255, 255), width=3)
            draw.text((x-12, y-8), "БП", fill=(255, 255, 255), font=font_small)
        else:
            # Задвижка - зелёный круг
            draw.ellipse([x-18, y-18, x+18, y+18], 
                        fill=(0, 180, 0), outline=(255, 255, 255), width=3)
            draw.text((x-8, y-8), "З", fill=(255, 255, 255), font=font_small)
    
    # Рисуем дефекты
    defect_radius = 10
    for idx, row in defects_df.iterrows():
        if 'scheme_x' not in row or 'scheme_y' not in row:
            continue
        
        x = int(row['scheme_x'])
        y = int(row['scheme_y'])
        risk = row.get('risk_class', 'Low')
        
        color = RISK_COLORS.get(risk, (128, 128, 128))
        
        # Рисуем точку дефекта с белой обводкой
        draw.ellipse([x-defect_radius-2, y-defect_radius-2, 
                     x+defect_radius+2, y+defect_radius+2], 
                    fill=(255, 255, 255), outline=(0, 0, 0), width=1)
        draw.ellipse([x-defect_radius, y-defect_radius, 
                     x+defect_radius, y+defect_radius], 
                    fill=color, outline=(255, 255, 255), width=2)
        
        # Номер дефекта
        defect_id = str(row.get('identification', str(idx+1)))[:8]
        if pd.notna(defect_id):
            # Белый фон для текста
            text_bbox = draw.textbbox((0, 0), defect_id, font=font_tiny)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            text_x = x + defect_radius + 3
            text_y = y - text_height // 2
            
            draw.rectangle([text_x-1, text_y-1, text_x+text_width+1, text_y+text_height+1],
                          fill=(255, 255, 255), outline=(0, 0, 0), width=1)
            draw.text((text_x, text_y), defect_id, fill=(0, 0, 0), font=font_tiny)
    
    # Легенда в правом нижнем углу
    img_width, img_height = img.size
    legend_width, legend_height = 180, 110
    legend_x = img_width - legend_width - 20
    legend_y = img_height - legend_height - 20
    
    # Полупрозрачный белый фон для легенды
    draw.rectangle([legend_x, legend_y, legend_x+legend_width, legend_y+legend_height], 
                  fill=(255, 255, 255, 230), outline=(0, 0, 0), width=2)
    
    draw.text((legend_x+10, legend_y+8), "Легенда:", fill=(0, 0, 0), font=font)
    
    y_offset = 32
    for risk, color in RISK_COLORS.items():
        draw.ellipse([legend_x+12, legend_y+y_offset, 
                     legend_x+24, legend_y+y_offset+12], 
                    fill=color, outline=(0, 0, 0), width=1)
        
        risk_names = {'High': 'Высокий', 'Medium': 'Средний', 'Low': 'Низкий'}
        draw.text((legend_x+32, legend_y+y_offset-2), 
                 risk_names.get(risk, risk), fill=(0, 0, 0), font=font_small)
        y_offset += 24
    
    # Сохраняем
    img.save(output_path, quality=95)
    return output_path


def get_defect_at_position(defects_df: pd.DataFrame, click_x: int, click_y: int, 
                          tolerance: int = 15) -> Dict:
    """
    Находит дефект по координатам клика
    
    Args:
        defects_df: DataFrame с дефектами
        click_x, click_y: координаты клика
        tolerance: радиус поиска в пикселях
    
    Returns:
        информация о дефекте или None
    """
    if 'scheme_x' not in defects_df.columns or 'scheme_y' not in defects_df.columns:
        return None
    
    for idx, row in defects_df.iterrows():
        distance = calculate_distance(click_x, click_y, row['scheme_x'], row['scheme_y'])
        
        if distance <= tolerance:
            return {
                'index': idx,
                'data': row.to_dict(),
                'distance': distance
            }
    
    return None
