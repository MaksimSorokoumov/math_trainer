import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
import random
from functools import partial
import json
import os
from kivy.uix.slider import Slider
from kivy.core.audio import SoundLoader
from kivy.uix.progressbar import ProgressBar
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.metrics import dp

kivy.require('2.0.0')

# Словарь с последовательностями для каждой таблицы
LEARNING_SEQUENCES = {}
for n in range(2, 10):
    sequence = []
    for i in range(1, 10):
        # Добавляем пример на умножение
        sequence.append((n, i, '*'))
        # Добавляем пример на деление
        sequence.append((n * i, n, '/'))
    LEARNING_SEQUENCES[n] = sequence


class LearningScreen(Screen):
    """Экран пошагового изучения выбранной таблицы"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mastery_examples = []
        self.current_example = None
        self.time_limit = App.get_running_app().time_limit
        self.remaining_time = self.time_limit
        self.timer_event = None
        self.session_active = False
        self.click_sound = SoundLoader.load('click.wav')
        # Загружаем звуки ошибок
        self.fail_sounds = []
        for i in range(1, 6):
            sound = SoundLoader.load(f'fail{i}.wav')
            if sound:
                self.fail_sounds.append(sound)
        
        # Загружаем мотивационные звуки
        self.good_sounds = []
        for i in range(1, 6):
            sound = SoundLoader.load(f'good{i}.wav')
            if sound:
                self.good_sounds.append(sound)
        
        # Счетчики для мотивационных триггеров
        self.correct_streak = 0  # Серия правильных ответов подряд
        self.fast_answers = 0    # Количество быстрых ответов подряд
        self.session_correct = 0 # Правильных ответов в текущей сессии
        self.current_score = App.get_running_app().current_score
        self.target_score = 150 # Target score for stage 2
        self.current_stage = App.get_running_app().current_stage # 1 = mastery stage, 2 = score stage
        self.build_ui()

    def build_ui(self):
        # Основной макет. Используем dp для консистентности.
        # Добавляем отступ сверху dp(30), чтобы избежать наложения на статус бар.
        self.layout = BoxLayout(orientation='vertical', padding=[dp(10), dp(30), dp(10), dp(10)], spacing=dp(10))

        # Блок с прогресс-барами. Уменьшаем его высоту и внутренние отступы.
        self.progress_bars_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(120), spacing=dp(5))
        
        # Убираем дублирующую надпись, так как 'points_big_label' показывает ту же информацию.
        # self.points_progress_label = Label(text=f'Серия: {self.current_score}/{self.target_score}', size_hint_y=None, height='30dp', halign='left', valign='middle')
        
        # Уменьшаем высоту прогресс-бара
        self.points_progress_bar = ProgressBar(max=self.target_score, value=self.current_score, size_hint_y=None, height=dp(20))
        
        # Уменьшаем высоту и размер шрифта для крупной надписи с очками
        self.points_big_label = Label(text=f'Набрано {self.current_score} из {self.target_score}', 
                                     size_hint_y=None, height=dp(40), font_size='22sp', 
                                     halign='center', valign='middle', bold=True)
        
        # self.progress_bars_layout.add_widget(self.points_progress_label) # Убрали
        self.progress_bars_layout.add_widget(self.points_progress_bar)
        self.progress_bars_layout.add_widget(self.points_big_label)

        # Прогресс изучения со звездами. Делаем компактнее.
        self.mastery_progress_label = Label(text='Прогресс изучения: 0/0', size_hint_y=None, height=dp(20), halign='left', valign='middle')
        # Уменьшаем высоту блока со звездами, чтобы они были в один ряд.
        self.mastery_stars_layout = GridLayout(cols=9, size_hint_y=None, height=dp(30), spacing=dp(3))
        self.progress_bars_layout.add_widget(self.mastery_progress_label)
        self.progress_bars_layout.add_widget(self.mastery_stars_layout)

        self.layout.add_widget(self.progress_bars_layout)

        # Уменьшаем кнопки Старт/Стоп
        session_controls = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(45), spacing=dp(10))
        self.start_button = Button(text='Старт', background_color=(0, 1, 0, 1))
        self.start_button.bind(on_press=self.start_session)
        session_controls.add_widget(self.start_button)

        self.stop_button = Button(text='Стоп', background_color=(1, 0, 0, 1), disabled=True)
        self.stop_button.bind(on_press=self.stop_session)
        session_controls.add_widget(self.stop_button)
        self.layout.add_widget(session_controls)

        # Уменьшаем заголовок
        self.title_label = Label(text='', font_size='18sp', size_hint_y=None, height=dp(35))
        self.layout.add_widget(self.title_label)

        # Уменьшаем блок вопроса и шрифт
        self.question_label = Label(text='', font_size='40sp', size_hint_y=None, height=dp(90))
        self.layout.add_widget(self.question_label)

        # Уменьшаем поле ввода ответа
        self.answer_input = TextInput(hint_text='Ваш ответ', font_size='28sp', multiline=False,
                                       input_filter='int', size_hint_y=None, height=dp(60),
                                       halign='center', readonly=True)
        self.answer_input.bind(on_text_validate=self.check_answer)
        self.layout.add_widget(self.answer_input)

        # Уменьшаем клавиатуру и отступы между кнопками
        self.keyboard_layout = GridLayout(cols=3, spacing=dp(5), size_hint_y=None, height=dp(220))
        
        # Кнопки цифр 1-9
        for i in range(1, 10):
            btn = Button(text=str(i), font_size='24sp')
            btn.bind(on_press=lambda instance, digit=str(i): self.add_digit(digit))
            self.keyboard_layout.add_widget(btn)
        
        # Дополнительные кнопки
        clear_btn = Button(text='Очистить', font_size='18sp', background_color=(0, 0, 1, 1))
        clear_btn.bind(on_press=self.clear_input)
        self.keyboard_layout.add_widget(clear_btn)
        
        zero_btn = Button(text='0', font_size='24sp')
        zero_btn.bind(on_press=lambda instance: self.add_digit('0'))
        self.keyboard_layout.add_widget(zero_btn)
        
        check_btn = Button(text='Проверить', font_size='18sp', background_color=(0, 1, 0, 1))
        check_btn.bind(on_press=self.check_answer)
        self.keyboard_layout.add_widget(check_btn)
        
        self.layout.add_widget(self.keyboard_layout)

        # Уменьшаем блок обратной связи и таймера
        self.feedback_label = Label(text='', font_size='20sp', size_hint_y=None, height=dp(35))
        self.layout.add_widget(self.feedback_label)
        
        self.timer_label = Label(text=f'Время: {self.time_limit}', font_size='20sp', size_hint_y=None, height=dp(35))
        self.layout.add_widget(self.timer_label)

        # Уменьшаем нижние кнопки
        buttons_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(45), spacing=dp(10))
        
        settings_btn = Button(text='Настройки')
        settings_btn.bind(on_press=self.open_settings_popup)
        buttons_layout.add_widget(settings_btn)

        back_btn = Button(text='Выйти')
        back_btn.bind(on_press=self.go_back)
        buttons_layout.add_widget(back_btn)

        self.layout.add_widget(buttons_layout)

        self.add_widget(self.layout)
        self.toggle_session_widgets(False)
        self.update_progress_bars()

    def play_fail_sound(self):
        """Воспроизводит случайный звук ошибки"""
        if self.fail_sounds:
            fail_sound = random.choice(self.fail_sounds)
            fail_sound.play()

    def play_good_sound(self):
        """Воспроизводит случайный мотивационный звук"""
        if self.good_sounds:
            good_sound = random.choice(self.good_sounds)
            good_sound.play()

    def show_motivational_popup(self, title, message):
        """Показывает мотивационное сообщение с звуком"""
        self.play_good_sound()
        
        label = Label(text=message, halign='center', valign='middle', text_size=(None, None))
        
        popup = Popup(title=title,
                      content=label,
                      size_hint=(0.8, 0.4),
                      auto_dismiss=True)
        
        # Устанавливаем text_size после создания popup
        def set_text_size(instance, size):
            label.text_size = (size[0] * 0.9, None)
        
        popup.bind(size=set_text_size)
        
        # Автоматически закрываем через 2 секунды
        Clock.schedule_once(lambda dt: popup.dismiss(), 2.0)
        popup.open()

    def check_motivational_triggers(self, is_correct, answer_time):
        """Проверяет условия для показа мотивационных сообщений"""
        if not is_correct:
            self.correct_streak = 0
            self.fast_answers = 0
            return
        
        self.correct_streak += 1
        self.session_correct += 1
        
        # Быстрый ответ (меньше 3 секунд)
        if answer_time <= 3:
            self.fast_answers += 1
        else:
            self.fast_answers = 0
        
        # Мотивационные сообщения только в первом этапе (изучение)
        if self.current_stage != 1:
            return
        
        # Триггер 1: Серия из 25 правильных ответов подряд (только в этапе 1)
        if self.correct_streak == 25:
            messages = [
                "Отлично! 25 правильных ответов подряд!",
                "Великолепно! Ты в ударе!",
                "Потрясающе! Продолжай в том же духе!",
                "Браво! Ты настоящий математик!"
            ]
            self.show_motivational_popup("🎉 Серия!", random.choice(messages))
        
        # Триггер 2: Особые достижения в этапе изучения (только в этапе 1)
        # Проверяем прогресс изучения
        mastered_count = sum(1 for ex in self.mastery_examples if ex['consecutive_correct'] >= ex['correct_needed'])
        total_examples = len(self.mastery_examples)
        
        # При достижении 50% изучения
        progress_percent = (mastered_count / total_examples * 100) if total_examples > 0 else 0
        
        if progress_percent >= 50 and not hasattr(self, 'shown_50'):
            self.shown_50 = True
            self.show_motivational_popup("🎯 Половина!", "Половина изучена! Ты справляешься!")

    def show_timer(self):
        """Показать таймер, скрыть обратную связь"""
        self.timer_label.opacity = 1
        self.feedback_label.opacity = 0

    def show_feedback(self):
        """Показать обратную связь, скрыть таймер"""
        self.timer_label.opacity = 0
        self.feedback_label.opacity = 1

    def update_stars_images(self, mastered_count, total_examples):
        """Обновляет изображения звездочек для отображения прогресса"""
        print(f"update_stars_images вызван: mastered={mastered_count}, total={total_examples}")
        
        # Очищаем старые изображения
        self.mastery_stars_layout.clear_widgets()
        
        if total_examples == 0:
            print("total_examples равно 0, выходим")
            return
        
        # Ограничиваем количество звездочек для лучшего отображения
        max_stars = min(total_examples, 18)  # Максимум 18 звездочек (2 строки по 9)
        
        # Вычисляем сколько звездочек должно быть заполнено
        filled_stars = int((mastered_count / total_examples) * max_stars) if total_examples > 0 else 0
        
        print(f"Создаем {max_stars} звезд, из них {filled_stars} заполненных")
        
        # Создаем изображения звездочек
        for i in range(max_stars):
            if i < filled_stars:
                # Заполненная звезда
                star_img = self.create_filled_star_image()
            else:
                # Пустая звезда
                star_img = self.create_empty_star_image()
            
            self.mastery_stars_layout.add_widget(star_img)
    
    def create_filled_star_image(self):
        """Создает изображение заполненной звезды"""
        try:
            # Используем абсолютный путь
            star_path = os.path.join(os.path.dirname(__file__), 'star_filled.png')
            print(f"Путь к заполненной звезде: {star_path}")
            print(f"Файл существует: {os.path.exists(star_path)}")
            
            img = Image(source=star_path, size_hint=(1, 1), allow_stretch=True, keep_ratio=True)  # Используем размер ячейки GridLayout
            print(f"Загружена заполненная звезда: {img.source}")
            return img
        except Exception as e:
            print(f"Ошибка загрузки star_filled.png: {e}")
            # Если изображение не найдено, создаем простой лейбл
            return Label(text='★', font_size='16sp', color=(1, 1, 0, 1), halign='center', valign='middle')
    
    def create_empty_star_image(self):
        """Создает изображение пустой звезды"""
        try:
            # Используем абсолютный путь
            star_path = os.path.join(os.path.dirname(__file__), 'star_empty.png')
            print(f"Путь к пустой звезде: {star_path}")
            print(f"Файл существует: {os.path.exists(star_path)}")
            
            img = Image(source=star_path, size_hint=(1, 1), allow_stretch=True, keep_ratio=True)  # Используем размер ячейки GridLayout
            print(f"Загружена пустая звезда: {img.source}")
            return img
        except Exception as e:
            print(f"Ошибка загрузки star_empty.png: {e}")
            # Если изображение не найдено, создаем простой лейбл
            return Label(text='☆', font_size='16sp', color=(0.5, 0.5, 0.5, 1), halign='center', valign='middle')

    def toggle_session_widgets(self, active):
        """Enable/disable widgets based on session state."""
        self.keyboard_layout.disabled = not active
        self.answer_input.disabled = not active
        self.question_label.opacity = 1 if active else 0
        self.progress_bars_layout.opacity = 1 if active else 0
        
        if active:
            # Во время сессии показываем таймер, скрываем обратную связь
            self.timer_label.opacity = 1
            self.feedback_label.opacity = 0
        else:
            # Вне сессии скрываем и таймер, и обратную связь
            self.timer_label.opacity = 0
            self.feedback_label.opacity = 0

    def start_session(self, instance):
        if self.session_active:
            return
        self.session_active = True
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.toggle_session_widgets(True)

        app = App.get_running_app()
        table_num = getattr(app, 'current_learning_table', 2)
        self.current_stage = getattr(app, 'current_stage', 1)
        
        # Сбрасываем счетчики мотивации
        self.correct_streak = 0
        self.fast_answers = 0
        self.session_correct = 0
        # Сбрасываем флаг показанного сообщения прогресса
        if hasattr(self, 'shown_50'):
            delattr(self, 'shown_50')
        
        if self.current_stage == 1:
            # Stage 1: Mastery of current table examples
            self.mastery_examples = self.get_examples_for_table(table_num, for_mastery=True)
            random.shuffle(self.mastery_examples)
            self.current_score = 0  # Reset score for stage 1
        else:
            # Stage 2: Score accumulation with all learned tables
            self.current_score = app.current_score
        
        self.feedback_label.text = ''
        self.answer_input.text = ''
        self.show_timer()  # Показываем таймер в начале сессии
        self.update_progress_bars()
        self.show_current_question()

    def stop_session(self, instance=None):
        if not self.session_active:
            return
        self.session_active = False
        self.stop_timer()

        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.toggle_session_widgets(False)
        
        app = App.get_running_app()
        table_num = getattr(app, 'current_learning_table', 2)
        stage_text = "Этап 1: Изучение" if self.current_stage == 1 else "Этап 2: Серия"
        self.title_label.text = f'Таблица на {table_num} ({stage_text})'
        self.question_label.text = 'Нажмите "Старт" для начала'
        self.answer_input.text = ''
        self.feedback_label.text = ''
        self.update_progress_bars()

    def open_settings_popup(self, instance):
        self.stop_session()
        app = App.get_running_app()

        # Контейнер содержимого попапа. size_hint_y=None, чтобы высота сама подстраивалась под детей,
        # благодаря чему не остается лишнего пустого пространства в верхней части окна.
        content = BoxLayout(orientation='vertical', padding=10, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        title_label = Label(text='Длительность таймера (сек)', size_hint_y=None, height=40)
        content.add_widget(title_label)
        
        slider_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        slider_value_label = Label(text=str(int(app.time_limit)), size_hint_x=0.2)
        
        slider = Slider(min=5, max=8, value=app.time_limit, step=1)
        
        def update_label(instance, value):
            slider_value_label.text = str(int(value))
        
        slider.bind(value=update_label)
        
        slider_layout.add_widget(slider)
        slider_layout.add_widget(slider_value_label)
        content.add_widget(slider_layout)
        
        close_button = Button(text='Сохранить и закрыть', size_hint_y=None, height=50)
        content.add_widget(close_button)

        # Задаём фиксированную, но компактную высоту попапа, чтобы элементы размещались плотнее друг к другу.
        popup = Popup(title='Настройки',
                      content=content,
                      size_hint=(0.8, None),
                      height=dp(220))

        def save_and_close(instance):
            new_time_limit = int(slider.value)
            app.time_limit = new_time_limit
            self.time_limit = new_time_limit
            
            app.save_progress()
            popup.dismiss()

        close_button.bind(on_press=save_and_close)
        
        popup.open()

    def get_examples_for_table(self, table_num, for_mastery=False):
        examples = []
        for i in range(1, 10):
            # Умножение
            ex_mul = {'a': table_num, 'b': i, 'op': '*', 'table': table_num}
            if for_mastery:
                ex_mul.update({'consecutive_correct': 0, 'correct_needed': 5})
            examples.append(ex_mul)
            # Деление
            ex_div = {'a': table_num * i, 'b': table_num, 'op': '/', 'table': table_num}
            if for_mastery:
                ex_div.update({'consecutive_correct': 0, 'correct_needed': 5})
            examples.append(ex_div)
        return examples

    # --- Логика экрана --- #

    def on_pre_enter(self):
        """Подготовка перед показом экрана"""
        self.stop_session()

    def start_timer(self):
        self.stop_timer()
        self.remaining_time = self.time_limit
        self.timer_label.text = f'Время: {self.remaining_time}'
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def update_timer(self, dt):
        self.remaining_time -= 1
        self.timer_label.text = f'Время: {self.remaining_time}'
        if self.remaining_time <= 0:
            self.handle_timeout()

    def handle_timeout(self):
        self.stop_timer()
        if not self.current_example or not self.session_active:
            return

        if self.current_stage == 1:
            # Stage 1: Reset consecutive correct count
            app = App.get_running_app()
            table_num = app.current_learning_table
            if self.current_example.get('table') == table_num:
                self.current_example['consecutive_correct'] = 0
        else:
            # Stage 2: Deduct points for timeout (10 points)
            self.current_score -= 10
            if self.current_score < 0:
                self.current_score = 0

        a = self.current_example['a']
        b = self.current_example['b']
        op = self.current_example['op']

        if op == '*':
            correct_answer = a * b
        else:
            correct_answer = a // b
            
        self.feedback_label.text = f'Время вышло! Ответ: {correct_answer}'
        self.feedback_label.color = (1, 0, 0, 1)
        self.show_feedback()  # Показываем обратную связь
        
        # Воспроизводим звук ошибки
        self.play_fail_sound()
        
        # Проверяем мотивационные триггеры (для сброса счетчиков)
        self.check_motivational_triggers(False, self.time_limit)

        App.get_running_app().current_score = self.current_score
        App.get_running_app().save_progress()

        self.update_progress_bars()
        Clock.schedule_once(self.show_current_question, 1.0)

    def update_progress_bars(self):
        if self.current_stage == 1:
            # Stage 1: Show mastery progress with star images, hide points progress
            self.points_progress_bar.opacity = 0
            self.points_big_label.opacity = 0
            self.mastery_progress_label.opacity = 1
            self.mastery_stars_layout.opacity = 1
            
            mastered_count = sum(1 for ex in self.mastery_examples if ex['consecutive_correct'] >= ex['correct_needed'])
            total_examples = len(self.mastery_examples)
            
            # Обновляем изображения звездочек
            self.update_stars_images(mastered_count, total_examples)
            self.mastery_progress_label.text = f'Прогресс изучения: {mastered_count}/{total_examples}'
        else:
            # Stage 2: Show points progress, hide mastery progress
            self.points_progress_bar.opacity = 1
            self.points_big_label.opacity = 1
            self.mastery_progress_label.opacity = 0
            self.mastery_stars_layout.opacity = 0
            
            self.points_progress_bar.value = self.current_score
            self.points_big_label.text = f'Набрано {self.current_score} из {self.target_score}'

    def show_current_question(self, dt=0):
        self.stop_timer()

        if self.current_stage == 1:
            # Stage 1: Mastery stage
            unmastered_examples = [ex for ex in self.mastery_examples if ex['consecutive_correct'] < ex['correct_needed']]
            
            if not unmastered_examples:
                # All examples mastered, move to stage 2
                self.show_mastery_complete_popup()
                return
            
            self.current_example = random.choice(unmastered_examples)
            app = App.get_running_app()
            table_num = app.current_learning_table
            self.title_label.text = f'Таблица на {table_num} (Этап 1: Изучение)'
        else:
            # Stage 2: Score accumulation stage
            app = App.get_running_app()
            table_num = app.current_learning_table
            
            if self.current_score >= self.target_score:
                self.show_finish_popup()
                return
            
            # Choose examples from current and previous tables
            all_examples = []
            for t in range(2, table_num + 1):
                all_examples.extend(self.get_examples_for_table(t))
            
            self.current_example = random.choice(all_examples)
            self.title_label.text = f'Таблица на {table_num} (Этап 2: МАРАФОН)'

        if self.click_sound:
            self.click_sound.play()
        
        a = self.current_example['a']
        b = self.current_example['b']
        op = self.current_example['op']

        if op == '*':
            self.question_label.text = f'{a} × {b} = ?'
        else:
            self.question_label.text = f'{a} ÷ {b} = ?'

        self.answer_input.text = ''
        self.feedback_label.text = ''
        self.show_timer()  # Показываем таймер для нового вопроса
        self.start_timer()
        self.update_progress_bars()

    def show_mastery_complete_popup(self):
        self.stop_timer()
        app = App.get_running_app()
        current_table = getattr(app, 'current_learning_table', 2)
        
        message_text = f'''Молодец, ты выучил таблицу №{current_table}, теперь новый этап "МАРАФОН".

Набери {self.target_score} очков чтобы перейти к изучению следующей таблицы!

Время на ответ: 7 секунд
За правильный ответ: +1 очко
Неправильный ответ: -15 очков
Не успеешь ответить: -10 очков'''
        
        # Создаем контент с кнопкой
        content_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        label = Label(text=message_text, 
                     halign='center', valign='middle', text_size=(None, None))
        content_layout.add_widget(label)
        
        # Добавляем кнопку для перехода к марафону
        start_button = Button(text='Начать МАРАФОН!', size_hint_y=None, height='50dp',
                             background_color=(0, 0.8, 0, 1))  # Зеленый цвет
        content_layout.add_widget(start_button)
        
        popup = Popup(title='🏆 Этап завершен!',
                      content=content_layout,
                      size_hint=(0.9, 0.8),  # Увеличиваем размер для кнопки
                      auto_dismiss=False)  # Отключаем автозакрытие при клике вне окна
        
        # Устанавливаем text_size после создания popup для правильного расчета размеров
        def set_text_size(instance, size):
            label.text_size = (size[0] * 0.9, None)  # 90% от ширины popup
        
        popup.bind(size=set_text_size)
        
        def start_stage_2(instance):
            app.current_stage = 2
            app.current_score = 0
            self.current_stage = 2
            self.current_score = 0
            app.save_progress()
            popup.dismiss()
            self.start_session(None)
        
        start_button.bind(on_press=start_stage_2)
        popup.open()

    def check_answer(self, instance=None):
        if not self.session_active:
            return
        
        # Вычисляем время ответа
        answer_time = self.time_limit - self.remaining_time
        
        self.stop_timer()
        if not self.current_example:
            return

        answer_text = self.answer_input.text.strip()
        if not answer_text.isdigit():
            self.feedback_label.text = 'Введите число'
            self.feedback_label.color = (1, 0, 0, 1)
            self.show_feedback()  # Показываем обратную связь
            Clock.schedule_once(lambda dt: self.show_timer(), 1.0)  # Через секунду возвращаем таймер
            self.start_timer()
            return

        user_answer = int(answer_text)
        a = self.current_example['a']
        b = self.current_example['b']
        op = self.current_example['op']
        app = App.get_running_app()
        table_num = app.current_learning_table
        
        if op == '*':
            correct_answer = a * b
        else:
            correct_answer = a // b

        is_correct = user_answer == correct_answer

        if is_correct:
            self.feedback_label.text = 'Правильно!'
            self.feedback_label.color = (0, 1, 0, 1)
            self.show_feedback()  # Показываем обратную связь
            
            if self.current_stage == 1:
                # Stage 1: Increment consecutive correct count
                if self.current_example.get('table') == table_num:
                    self.current_example['consecutive_correct'] += 1
            else:
                # Stage 2: Increment score
                self.current_score += 1
            
            # Проверяем мотивационные триггеры
            self.check_motivational_triggers(True, answer_time)
            
            Clock.schedule_once(self.show_current_question, 1.0)
        else:
            self.feedback_label.text = f'Неверно! Ответ: {correct_answer}'
            self.feedback_label.color = (1, 0, 0, 1)
            self.show_feedback()  # Показываем обратную связь
            
            # Воспроизводим звук ошибки
            self.play_fail_sound()
            
            if self.current_stage == 1:
                # Stage 1: Reset consecutive correct count
                if self.current_example.get('table') == table_num:
                    self.current_example['consecutive_correct'] = 0
            else:
                # Stage 2: Deduct points for incorrect answer (15 points)
                self.current_score -= 15
                if self.current_score < 0:
                    self.current_score = 0
            
            # Проверяем мотивационные триггеры (для сброса счетчиков)
            self.check_motivational_triggers(False, answer_time)
            
            Clock.schedule_once(self.show_current_question, 1.0)
        
        App.get_running_app().current_score = self.current_score
        App.get_running_app().save_progress()
        self.update_progress_bars()

    def show_finish_popup(self):
        self.stop_timer()
        app = App.get_running_app()
        current_table = getattr(app, 'current_learning_table', 2)

        if current_table < 9:
            app.current_learning_table += 1
            app.current_stage = 1  # Reset to stage 1 for new table
            app.current_score = 0
            app.save_progress()
            
            label = Label(text=f'Вы завершили таблицу на {current_table}!\nПереходим к таблице на {app.current_learning_table}!', 
                         halign='center', valign='middle', text_size=(None, None))
            
            popup = Popup(title='Отлично!',
                          content=label,
                          size_hint=(0.8, 0.5))
            
            # Устанавливаем text_size после создания popup для правильного расчета размеров
            def set_text_size(instance, size):
                label.text_size = (size[0] * 0.9, None)  # 90% от ширины popup
            
            popup.bind(size=set_text_size)
            popup.open()
            popup.bind(on_dismiss=lambda *args: self.manager.current == 'learning' and self.on_pre_enter())
        else:
            label = Label(text=f'Вы изучили все таблицы умножения от 2 до 9!\nВаш финальный результат: серия из {self.current_score} правильных ответов!', 
                         halign='center', valign='middle', text_size=(None, None))
            
            popup = Popup(title='Поздравляем!',
                          content=label,
                          size_hint=(0.8, 0.5))
            
            # Устанавливаем text_size после создания popup для правильного расчета размеров
            def set_text_size(instance, size):
                label.text_size = (size[0] * 0.9, None)  # 90% от ширины popup
            
            popup.bind(size=set_text_size)
            popup.open()
            popup.bind(on_dismiss=lambda *args: app.reset_learning_progress())
            popup.bind(on_dismiss=lambda *args: self.manager.current == 'learning' and self.on_pre_enter())

    def go_back(self, *args):
        self.stop_session()
        self.stop_timer()
        App.get_running_app().stop()

    def add_digit(self, digit):
        if not self.session_active:
            return
        self.answer_input.text += digit

    def clear_input(self, instance):
        if not self.session_active:
            return
        self.answer_input.text = ''


class LearningApp(App):
    current_learning_table = 2
    time_limit = 7
    current_score = 0
    current_stage = 1  # 1 = mastery stage, 2 = score stage
    PROGRESS_FILE = 'progress.json'

    def build(self):
        self.load_progress()
        self.title = 'Изучение таблицы умножения'
        sm = ScreenManager()
        sm.add_widget(LearningScreen(name='learning'))
        return sm
    
    def on_stop(self):
        self.save_progress()

    def save_progress(self):
        try:
            progress_data = {
                'current_learning_table': self.current_learning_table,
                'time_limit': self.time_limit,
                'current_score': self.current_score,
                'current_stage': self.current_stage
            }
            with open(self.PROGRESS_FILE, 'w') as f:
                json.dump(progress_data, f)
        except IOError as e:
            print(f"Ошибка сохранения прогресса: {e}")

    def load_progress(self):
        if os.path.exists(self.PROGRESS_FILE):
            try:
                with open(self.PROGRESS_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.current_learning_table = data.get('current_learning_table', 2)
                        self.time_limit = data.get('time_limit', 7)
                        self.current_score = data.get('current_score', 0)
                        self.current_stage = data.get('current_stage', 1)
                    else:
                        self.current_learning_table = 2
                        self.time_limit = 7
                        self.current_score = 0
                        self.current_stage = 1
            except (IOError, json.JSONDecodeError):
                self.current_learning_table = 2
                self.time_limit = 7
                self.current_score = 0
                self.current_stage = 1
        else:
            self.current_learning_table = 2
            self.time_limit = 7
            self.current_score = 0
            self.current_stage = 1

    def reset_learning_progress(self):
        self.current_learning_table = 2
        self.current_score = 0
        self.current_stage = 1
        self.save_progress()


if __name__ == '__main__':
    LearningApp().run() 