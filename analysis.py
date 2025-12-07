import pandas as pd
import numpy as np
from typing import Dict

# Константы для классификации риска
RISK_THRESHOLDS = {
    'erf_high_risk': 0.8,
    'erf_medium_risk': 0.5,
    'wall_thickness_critical': 3.0,  # мм
    'depth_critical': 40,  # %
    'depth_high': 25  # %
}

# Маппинг колонок из Excel в нормализованные имена
COLUMN_MAPPING = {
    '№ секции': 'section_id',
    'длина секции [м]': 'section_length_m',
    'прив.ТС [мм]': 'wall_thickness_mm',
    'расст. до шва против теч. [м]': 'distance_to_weld_m',
    'измер. расст. [м]': 'measured_distance_m',
    'тип аномалии': 'anomaly_type',
    'идентификация': 'identification',
    'комментарий': 'comment',
    'ориентация': 'orientation',
    'длина [мм]': 'defect_length_mm',
    'ширина [мм]': 'defect_width_mm',
    'глубина [%]': 'depth_pct',
    'средняя глубина [%]': 'depth_avg_pct',
    'абс. глубина [мм]': 'depth_abs_mm',
    'остат. ТС [мм]': 'wall_thickness_remaining_mm',
    'рез. глубина [%]': 'depth_result_pct',
    'уменьш. ВД [%]': 'pressure_reduction_pct',
    'ERF B31G': 'erf_b31g',
    'ERF (случай 1)': 'erf_case1',
    'ERF (случай 2)': 'erf_case2',
    'ERF DNV': 'erf_dnv',
    'локация на поверхн.': 'surface_location',
    'класс лок.': 'local_class',
    'Ремонт': 'repair_flag'
}


def clean_numeric(val):
    """Преобразует значение в число, обрабатывая запятые и пустые значения"""
    if pd.isna(val) or val == '':
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    
    # Преобразуем запятые в точки
    str_val = str(val).replace(',', '.').strip()
    try:
        return float(str_val)
    except:
        return np.nan


def normalize_defects(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Нормализует DataFrame из листа Excel "Аномалии подлежащие ремонту"
    """
    df = df_raw.copy()
    
    # Переименовываем колонки согласно маппингу
    rename_dict = {}
    for old_col in df.columns:
        for key, val in COLUMN_MAPPING.items():
            if key.lower() in str(old_col).lower():
                rename_dict[old_col] = val
                break
    
    df.rename(columns=rename_dict, inplace=True)
    
    # Список числовых колонок
    numeric_cols = [
        'section_length_m', 'wall_thickness_mm', 'distance_to_weld_m',
        'measured_distance_m', 'defect_length_mm', 'defect_width_mm',
        'depth_pct', 'depth_avg_pct', 'depth_abs_mm',
        'wall_thickness_remaining_mm', 'depth_result_pct',
        'pressure_reduction_pct', 'erf_b31g', 'erf_case1',
        'erf_case2', 'erf_dnv'
    ]
    
    # Применяем очистку к числовым колонкам
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
    
    # Убираем полностью пустые строки
    df.dropna(how='all', inplace=True)
    
    return df


def assign_risk_class(row) -> str:
    """
    Присваивает класс риска дефекту на основе правил
    """
    # Проверяем флаг ремонта
    repair_flag = str(row.get('repair_flag', '')).lower()
    if 'обязателен' in repair_flag or 'немедленн' in repair_flag:
        return 'High'
    
    # Проверяем ERF
    erf_b31g = row.get('erf_b31g', 1.0)
    erf_dnv = row.get('erf_dnv', 1.0)
    
    if pd.notna(erf_b31g) and erf_b31g < RISK_THRESHOLDS['erf_high_risk']:
        return 'High'
    if pd.notna(erf_dnv) and erf_dnv < RISK_THRESHOLDS['erf_high_risk']:
        return 'High'
    
    # Проверяем остаточную толщину стенки
    wall_remaining = row.get('wall_thickness_remaining_mm', 100)
    if pd.notna(wall_remaining) and wall_remaining < RISK_THRESHOLDS['wall_thickness_critical']:
        return 'High'
    
    # Проверяем глубину дефекта
    depth = row.get('depth_pct', 0)
    if pd.notna(depth) and depth > RISK_THRESHOLDS['depth_critical']:
        return 'High'
    
    # Средний риск
    if pd.notna(erf_b31g) and erf_b31g < RISK_THRESHOLDS['erf_medium_risk']:
        return 'Medium'
    if pd.notna(erf_dnv) and erf_dnv < RISK_THRESHOLDS['erf_medium_risk']:
        return 'Medium'
    if pd.notna(depth) and depth > RISK_THRESHOLDS['depth_high']:
        return 'Medium'
    
    return 'Low'


def compute_inspection_summary(defects_df: pd.DataFrame, inspection_meta: Dict) -> Dict:
    """
    Вычисляет агрегированную статистику по дефектам
    """
    # Присваиваем классы риска
    df = defects_df.copy()
    df['risk_class'] = df.apply(assign_risk_class, axis=1)
    
    # Присваиваем приоритет ремонта
    def assign_priority(row):
        if row['risk_class'] == 'High':
            return 1
        elif row['risk_class'] == 'Medium':
            return 2
        else:
            return 3
    
    df['repair_priority'] = df.apply(assign_priority, axis=1)
    
    # Агрегаты
    summary = {
        'overview': {
            'total_defects': len(df),
            'pipeline_name': inspection_meta.get('pipeline_name', 'N/A'),
            'segment_km': inspection_meta.get('segment_km', 'N/A'),
            'diameter_mm': inspection_meta.get('diameter_mm', 'N/A'),
            'method': inspection_meta.get('method', 'N/A'),
            'inspection_date': inspection_meta.get('start_date', 'N/A')
        },
        'by_risk': {
            'High': int((df['risk_class'] == 'High').sum()),
            'Medium': int((df['risk_class'] == 'Medium').sum()),
            'Low': int((df['risk_class'] == 'Low').sum())
        },
        'by_type': df['anomaly_type'].value_counts().to_dict() if 'anomaly_type' in df.columns else {},
        'by_repair_flag': df['repair_flag'].value_counts().to_dict() if 'repair_flag' in df.columns else {},
        'statistics': {
            'avg_depth_pct': float(df['depth_pct'].mean()) if 'depth_pct' in df.columns else None,
            'max_depth_pct': float(df['depth_pct'].max()) if 'depth_pct' in df.columns else None,
            'avg_erf_b31g': float(df['erf_b31g'].mean()) if 'erf_b31g' in df.columns else None,
            'min_erf_b31g': float(df['erf_b31g'].min()) if 'erf_b31g' in df.columns else None,
            'avg_wall_remaining_mm': float(df['wall_thickness_remaining_mm'].mean()) if 'wall_thickness_remaining_mm' in df.columns else None
        },
        'table': df
    }
    
    return summary


def compare_with_previous(current_summary: Dict, previous_summary: Dict) -> Dict:
    """
    Сравнивает текущую инспекцию с предыдущей
    """
    if not previous_summary:
        return {
            'defects_change': 0,
            'high_risk_change': 0,
            'has_previous': False
        }
    
    curr_total = current_summary['overview']['total_defects']
    prev_total = previous_summary['overview']['total_defects']
    
    curr_high = current_summary['by_risk']['High']
    prev_high = previous_summary['by_risk']['High']
    
    return {
        'defects_change': curr_total - prev_total,
        'high_risk_change': curr_high - prev_high,
        'defects_change_pct': round(((curr_total - prev_total) / prev_total * 100) if prev_total > 0 else 0, 1),
        'high_risk_change_pct': round(((curr_high - prev_high) / prev_high * 100) if prev_high > 0 else 0, 1),
        'has_previous': True
    }
