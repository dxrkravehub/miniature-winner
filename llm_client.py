import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

# Загружаем переменные из .env файла
load_dotenv()

def call_llm(system_prompt: str, user_prompt: str, context: dict = None) -> str:
    """
    Вызывает Google Gemini API для генерации текста
    
    Args:
        system_prompt: системный промпт с инструкциями
        user_prompt: запрос пользователя
        context: контекст с данными (будет сериализован в JSON)
    
    Returns:
        Сгенерированный текст
    """
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return "⚠️ GEMINI_API_KEY не установлен. Пожалуйста, добавьте ключ API в переменные окружения (.env файл)."
    
    try:
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Формируем полный промпт с контекстом
        full_prompt = f"{system_prompt}\n\n"
        
        if context:
            context_json = json.dumps(context, ensure_ascii=False, indent=2, default=str)
            full_prompt += f"ЗАДАЧА:\n{user_prompt}\n\nКОНТЕКСТ ДАННЫХ:\n```json\n{context_json}\n```"
        else:
            full_prompt += f"ЗАДАЧА:\n{user_prompt}"
        
        # Настройки генерации для более строгого и точного ответа
        generation_config = {
            'temperature': 0.2,  # Низкая температура для более детерминированных ответов
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 2048,
        }
        
        # Настройки безопасности (можно ослабить при необходимости)
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
        ]
        
        # Генерируем ответ
        response = model.generate_content(
            full_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Проверяем, был ли ответ заблокирован
        if response.prompt_feedback.block_reason:
            return f"⚠️ Ответ был заблокирован: {response.prompt_feedback.block_reason}"
        
        return response.text
    
    except Exception as e:
        return f"⚠️ Ошибка при вызове Gemini API: {str(e)}\n\nПроверьте:\n1. Правильность API ключа\n2. Наличие квоты на API\n3. Подключение к интернету"


def get_system_prompt() -> str:
    """Возвращает системный промпт для инженерного ассистента"""
    return """Ты — инженерный ассистент по анализу состояния трубопроводов.

КРИТИЧЕСКИ ВАЖНО:
- Ты НЕ придумываешь никакие цифры и факты
- Ты опираешься ТОЛЬКО на данные из предоставленного контекста
- Если информации нет в контексте — прямо говоришь об этом
- Ты объясняешь уже посчитанные результаты, а не делаешь собственные расчёты
- Твоя задача — интерпретировать данные для инженеров, а не принимать решения

Стиль ответа:
- Технический, но понятный
- Конкретный, без воды и общих фраз
- Структурированный (используй абзацы, но НЕ используй markdown заголовки)
- На русском языке
- Без вводных фраз типа "Конечно", "Хорошо" и т.п.
- Сразу к делу

Формат:
- Ответ должен быть готов для вставки в документ Word
- НЕ используй markdown заголовки (# ## ###)
- НЕ используй жирный текст (**текст**)
- Используй только обычный текст с абзацами
- Цифры и факты ТОЛЬКО из контекста

ЗАПРЕЩЕНО:
- Добавлять информацию, которой нет в контексте
- Делать предположения или догадки
- Использовать фразы "возможно", "вероятно", "предположительно"
- Говорить от первого лица ("я считаю", "я рекомендую")

ОБЯЗАТЕЛЬНО:
- Использовать только факты из контекста
- Указывать конкретные цифры
- Быть лаконичным (2-4 абзаца)
- Писать в безличной форме"""