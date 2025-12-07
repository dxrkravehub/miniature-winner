import pandas as pd
from typing import Tuple, Dict
import re
from datetime import datetime

def parse_inspection_csv(path: str) -> Tuple[Dict, pd.DataFrame]:
    """
    Парсит CSV файл с результатами магнитной дефектоскопии.
    
    Возвращает:
        - inspection_meta: метаданные обследования
        - coords_df: DataFrame с координатами и типами объектов
    """
    
    # Читаем файл с разделителем ;
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        raise ValueError("CSV файл пуст")
    
    # Первая строка - метаданные
    meta_line = lines[0].strip().split(';')
    
    inspection_meta = {
        'pipeline_name': meta_line[1] if len(meta_line) > 1 else 'Unknown',
        'diameter_mm': int(meta_line[2]) if len(meta_line) > 2 and meta_line[2].strip() else None,
        'segment_km': meta_line[3] if len(meta_line) > 3 else 'Unknown',
        'method': meta_line[6] if len(meta_line) > 6 else 'MFL',
        'start_date': None,
        'end_date': None
    }
    
    # Попытка извлечь даты (позиции 7 и 8)
    if len(meta_line) > 7 and meta_line[7].strip():
        try:
            inspection_meta['start_date'] = datetime.strptime(meta_line[7].strip(), '%d.%m.%Y')
        except:
            pass
    
    if len(meta_line) > 8 and meta_line[8].strip():
        try:
            inspection_meta['end_date'] = datetime.strptime(meta_line[8].strip(), '%d.%m.%Y')
        except:
            pass
    
    # Остальные строки - данные
    data_rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        
        fields = line.strip().split(';')
        if len(fields) < 20:  # Минимальная проверка
            continue
        
        try:
            # Пытаемся найти координаты в конце строки
            latitude = None
            longitude = None
            elevation = None
            
            # Ищем с конца, где обычно координаты
            for i in range(len(fields) - 1, max(0, len(fields) - 10), -1):
                if fields[i].strip():
                    val = fields[i].strip().replace(',', '.')
                    try:
                        num = float(val)
                        if 40 <= num <= 60 and latitude is None:  # Широта для региона
                            latitude = num
                        elif 50 <= num <= 70 and longitude is None:  # Долгота для региона
                            longitude = num
                        elif 200 <= num <= 400 and elevation is None:  # Высота
                            elevation = num
                    except:
                        pass
            
            if latitude is None or longitude is None:
                continue
            
            # Извлекаем chainage (обычно в начале, после ID секции)
            chainage_km = None
            for i in range(2, min(7, len(fields))):
                if fields[i].strip():
                    val = fields[i].strip().replace(',', '.')
                    try:
                        chainage_km = float(val)
                        break
                    except:
                        pass
            
            # Извлекаем тип объекта (текстовое поле в середине)
            raw_type = None
            raw_location = None
            
            for i in range(8, min(15, len(fields))):
                field_text = fields[i].strip().lower()
                if field_text and not field_text.replace(',', '.').replace('.', '').isdigit():
                    if any(keyword in field_text for keyword in ['коррозия', 'шов', 'металл', 'объект']):
                        raw_type = fields[i].strip()
                        break
            
            # Извлекаем локацию (обычно аббревиатура типа "ВНШ", "ВН")
            for i in range(12, min(18, len(fields))):
                field_text = fields[i].strip().upper()
                if field_text and len(field_text) <= 5 and field_text.isalpha():
                    if any(loc in field_text for loc in ['ВНШ', 'ВН', 'НН', 'ННШ']):
                        raw_location = field_text
                        break
            
            row_data = {
                'raw_section_id': fields[1] if len(fields) > 1 else None,
                'chainage_km': chainage_km,
                'raw_type': raw_type,
                'raw_location': raw_location,
                'latitude': latitude,
                'longitude': longitude,
                'elevation_m': elevation
            }
            
            data_rows.append(row_data)
            
        except Exception as e:
            # Пропускаем проблемные строки
            continue
    
    coords_df = pd.DataFrame(data_rows)
    
    return inspection_meta, coords_df
