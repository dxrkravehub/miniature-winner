"""
Модуль для анализа и объяснения дефектов с использованием LLM
"""

from llm_client import call_llm
from typing import Dict
import json


def explain_defect_location(defect_data: Dict, location_classification: str) -> str:
    """
    Использует LLM для объяснения, связан ли дефект с объектом инфраструктуры
    
    Args:
        defect_data: данные о дефекте (dict с полями типа depth_pct, erf_b31g и т.п.)
        location_classification: классификация места ("трубопровод-байпасс", "трубопровод-задвижка" и т.п.)
    
    Returns:
        текстовое объяснение от LLM
    """
    
    system_prompt = """Ты — эксперт по диагностике трубопроводов.

Твоя задача:
1. Определить, связан ли дефект с указанным объектом инфраструктуры
2. Объяснить вероятные причины дефекта
3. Дать краткую оценку (2-3 предложения)

ВАЖНО:
- Используй только данные из контекста
- Будь конкретным и технически точным
- Не придумывай информацию
- Опирайся на параметры дефекта (глубина, ERF, тип)"""

    user_prompt = f"""Проанализируй дефект и определи его связь с объектом инфраструктуры.

ДЕФЕКТ НАХОДИТСЯ РЯДОМ С: {location_classification}

Ответь на вопросы:
1. Связан ли этот дефект с объектом "{location_classification}"? (да/нет)
2. Какие характерные причины дефектов возникают в таких местах?
3. Что показывают параметры этого конкретного дефекта?

Формат ответа:
- Первая строка: СВЯЗЬ: Да/Нет
- Затем 2-3 предложения с объяснением"""

    context = {
        'location': location_classification,
        'defect_type': defect_data.get('anomaly_type', 'неизвестно'),
        'depth_pct': defect_data.get('depth_pct', 'нет данных'),
        'erf_b31g': defect_data.get('erf_b31g', 'нет данных'),
        'erf_dnv': defect_data.get('erf_dnv', 'нет данных'),
        'wall_thickness_remaining_mm': defect_data.get('wall_thickness_remaining_mm', 'нет данных'),
        'surface_location': defect_data.get('surface_location', 'нет данных'),
        'risk_class': defect_data.get('risk_class', 'нет данных'),
        'identification': defect_data.get('identification', 'нет данных')
    }
    
    response = call_llm(system_prompt, user_prompt, context)
    return response


def generate_defect_explanation(defect_data: Dict) -> str:
    """
    Генерирует полное объяснение дефекта
    
    Args:
        defect_data: полные данные о дефекте
    
    Returns:
        структурированное объяснение
    """
    
    system_prompt = """Ты — инженерный ассистент по анализу дефектов трубопроводов.

Задача: дать краткое, но полное объяснение дефекта.

Структура ответа:
1. Тип и локация дефекта
2. Оценка опасности (на основе ERF, глубины, остаточной толщины)
3. Вероятные причины
4. Рекомендации

Стиль: технический, конкретный, 3-4 абзаца."""

    user_prompt = """Проанализируй дефект и дай полное объяснение."""

    context = {
        'identification': defect_data.get('identification', 'N/A'),
        'anomaly_type': defect_data.get('anomaly_type', 'N/A'),
        'depth_pct': defect_data.get('depth_pct', 'N/A'),
        'depth_avg_pct': defect_data.get('depth_avg_pct', 'N/A'),
        'erf_b31g': defect_data.get('erf_b31g', 'N/A'),
        'erf_dnv': defect_data.get('erf_dnv', 'N/A'),
        'wall_thickness_remaining_mm': defect_data.get('wall_thickness_remaining_mm', 'N/A'),
        'surface_location': defect_data.get('surface_location', 'N/A'),
        'orientation': defect_data.get('orientation', 'N/A'),
        'risk_class': defect_data.get('risk_class', 'N/A'),
        'repair_flag': defect_data.get('repair_flag', 'N/A'),
        'infrastructure_location': defect_data.get('infrastructure_location', 'N/A'),
        'distance_to_infrastructure': defect_data.get('distance_to_infrastructure', 'N/A')
    }
    
    response = call_llm(system_prompt, user_prompt, context)
    return response


def batch_classify_defects_by_location(defects_df) -> Dict:
    """
    Массово классифицирует дефекты по связи с инфраструктурой
    
    Returns:
        dict с группировкой: {объект: [список дефектов]}
    """
    result = {}
    
    for idx, row in defects_df.iterrows():
        location = row.get('infrastructure_location', 'неизвестно')
        
        if location not in result:
            result[location] = []
        
        result[location].append({
            'index': idx,
            'identification': row.get('identification', f'DEF-{idx}'),
            'anomaly_type': row.get('anomaly_type', 'N/A'),
            'risk_class': row.get('risk_class', 'N/A'),
            'depth_pct': row.get('depth_pct', 'N/A'),
            'erf_b31g': row.get('erf_b31g', 'N/A')
        })
    
    return result
