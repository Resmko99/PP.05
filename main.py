import sys
import psycopg2
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QMessageBox, QInputDialog, QComboBox, QFormLayout, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

DB_PARAMS = {
    "dbname": "Hotel",
    "user": "postgres",
    "password": "1",
    "host": "localhost",
    "port": "5432"
}

DEFAULT_PASSWORD = "1234"
MAX_FAILED_ATTEMPTS = 3
LOGIN_BLOCK_PERIOD_DAYS = 30

def db_connect():
    return psycopg2.connect(**DB_PARAMS)

def clear_layout(layout):
    """Рекурсивная очистка компоновки и удаление всех виджетов."""
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                clear_layout(item.layout())

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Отель хазбра")
        self.resize(500, 300)
        self.center()
        self.init_ui()
        self.oldPos = self.pos()

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.frameGeometry()
        self.move(
            screen.center().x() - size.width() // 2,
            screen.center().y() - size.height() // 2
        )

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("Добро пожаловать!")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин")
        layout.addWidget(self.login_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)

        button_layout = QHBoxLayout()
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.authenticate_user)
        button_layout.addWidget(self.login_button)

        self.change_pass_btn = QPushButton("Сменить пароль")
        self.change_pass_btn.clicked.connect(self.open_change_password)
        button_layout.addWidget(self.change_pass_btn)
        layout.addLayout(button_layout)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)

        self.setLayout(layout)

    def authenticate_user(self):
        user_login = self.login_input.text().strip()
        user_password = self.password_input.text().strip()
        if not user_login or not user_password:
            self.error_label.setText("Все поля обязательны для заполнения")
            return

        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                SELECT user_id, first_name, last_name, user_password, block, login_date, failed_attempts, position_id 
                FROM Users 
                WHERE user_login = %s
            """
            cursor.execute(query, (user_login,))
            user = cursor.fetchone()
            if not user:
                self.error_label.setText("Неверный логин или пароль. Проверьте данные.")
                cursor.close()
                connection.close()
                return

            (user_id, first_name, last_name, db_password,
             block, login_date, failed_attempts, position_id) = user

            if block == 1:
                self.error_label.setText("Вы заблокированы. Обратитесь к администратору")
                cursor.close()
                connection.close()
                return

            if login_date and (datetime.now() - login_date) > timedelta(days=LOGIN_BLOCK_PERIOD_DAYS):
                cursor.execute("UPDATE Users SET block = 1 WHERE user_id = %s", (user_id,))
                connection.commit()
                self.error_label.setText("Вы заблокированы. Обратитесь к администратору")
                cursor.close()
                connection.close()
                return

            if user_password != db_password:
                failed_attempts = (failed_attempts or 0) + 1
                if failed_attempts >= MAX_FAILED_ATTEMPTS:
                    cursor.execute("UPDATE Users SET block = 1, failed_attempts = 0 WHERE user_id = %s", (user_id,))
                    connection.commit()
                    self.error_label.setText("Вы заблокированы. Обратитесь к администратору")
                else:
                    cursor.execute("UPDATE Users SET failed_attempts = %s WHERE user_id = %s", (failed_attempts, user_id))
                    connection.commit()
                    self.error_label.setText("Неверный логин или пароль. Проверьте данные.")
                cursor.close()
                connection.close()
                return

            cursor.execute("UPDATE Users SET failed_attempts = 0, login_date = %s WHERE user_id = %s",
                           (datetime.now(), user_id))
            connection.commit()
            cursor.close()
            connection.close()

            self.error_label.setStyleSheet("color: green;")
            self.error_label.setText("Авторизация успешна")
            QTimer.singleShot(1000, lambda: self.open_next_window(user_id, position_id))
        except Exception as e:
            self.error_label.setText(f"Ошибка подключения к БД: {e}")

    def open_next_window(self, user_id, position_id):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT user_password FROM Users WHERE user_id = %s", (user_id,))
            pwd = cursor.fetchone()[0]
            cursor.close()
            connection.close()
            if pwd == DEFAULT_PASSWORD:
                QMessageBox.information(self, "Смена пароля", "При первом входе требуется сменить пароль")
                self.change_password_window = ChangePasswordWindow(user_id)
                self.change_password_window.show()
            else:
                self.main_window = MainWindow(user_id, position_id)
                self.main_window.show()
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка открытия окна: {e}")

    def open_change_password(self):
        user_login = self.login_input.text().strip()
        if not user_login:
            QMessageBox.warning(self, "Внимание", "Введите логин для смены пароля")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT user_id FROM Users WHERE user_login = %s", (user_login,))
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            if result:
                user_id = result[0]
                self.change_password_window = ChangePasswordWindow(user_id)
                self.change_password_window.show()
            else:
                QMessageBox.warning(self, "Ошибка", "Пользователь не найден")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()


class ChangePasswordWindow(QWidget):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Смена пароля")
        self.resize(400, 300)
        self.center()
        self.init_ui()

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.frameGeometry()
        self.move(
            screen.center().x() - size.width() // 2,
            screen.center().y() - size.height() // 2
        )

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("Смените пароль")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.current_password = QLineEdit()
        self.current_password.setPlaceholderText("Текущий пароль")
        self.current_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.current_password)

        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Новый пароль")
        self.new_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.new_password)

        self.repeat_password = QLineEdit()
        self.repeat_password.setPlaceholderText("Подтвердите новый пароль")
        self.repeat_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.repeat_password)

        self.change_button = QPushButton("Изменить пароль")
        self.change_button.clicked.connect(self.change_password)
        layout.addWidget(self.change_button)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)

        self.setLayout(layout)

    def change_password(self):
        current = self.current_password.text().strip()
        new = self.new_password.text().strip()
        repeat = self.repeat_password.text().strip()
        if not current or not new or not repeat:
            self.message_label.setText("Все поля обязательны для заполнения")
            return
        if new != repeat:
            self.message_label.setText("Новые пароли не совпадают")
            return

        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT user_password FROM Users WHERE user_id = %s", (self.user_id,))
            db_current = cursor.fetchone()[0]
            if current != db_current:
                self.message_label.setText("Неверный текущий пароль")
                cursor.close()
                connection.close()
                return
            cursor.execute("UPDATE Users SET user_password = %s WHERE user_id = %s", (new, self.user_id))
            connection.commit()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Пароль успешно изменён")
            cursor.close()
            connection.close()
            QTimer.singleShot(1500, self.open_main_window)
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")

    def open_main_window(self):
        self.main_window = MainWindow(self.user_id, None)
        self.main_window.show()
        self.close()


class MainWindow(QWidget):
    def __init__(self, user_id, position_id):
        super().__init__()
        self.user_id = user_id
        self.position_id = position_id
        self.setWindowTitle("Рабочий стол HOTEL CompanyName")
        self.resize(1000, 700)
        self.setMinimumSize(600, 500)
        self.center()
        self.init_ui()

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.frameGeometry()
        self.move(
            screen.center().x() - size.width() // 2,
            screen.center().y() - size.height() // 2
        )

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.user_info_label = QLabel("")
        top_bar.addWidget(self.user_info_label)
        top_bar.addStretch()
        self.minimize_button = QPushButton("-")
        self.minimize_button.setFixedSize(40, 30)
        self.minimize_button.clicked.connect(self.showMinimized)
        top_bar.addWidget(self.minimize_button)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(40, 30)
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button)
        main_layout.addLayout(top_bar)

        self.content_layout = QVBoxLayout()
        main_layout.addLayout(self.content_layout)
        self.setLayout(main_layout)

        self.display_user_info()

    def display_user_info(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT first_name, last_name, email, position_id 
                FROM Users WHERE user_id = %s
            """, (self.user_id,))
            user = cursor.fetchone()
            if user:
                first_name, last_name, email, pos_id = user
                if not self.position_id:
                    self.position_id = pos_id
                cursor.execute("SELECT position_name FROM Position WHERE position_id = %s", (self.position_id,))
                pos = cursor.fetchone()
                pos_name = pos[0] if pos else ""
                self.user_info_label.setText(f"{pos_name}: {first_name} {last_name} ({email})")

                role_lower = pos_name.lower()
                if role_lower == "администратор":
                    self.show_admin_panel()
                elif role_lower == "менеджер":
                    self.show_manager_panel()
                elif role_lower == "пользователь":
                    self.show_user_panel()
                elif role_lower == "персонал":
                    self.show_staff_panel()
                else:
                    self.show_change_password_form()

            cursor.close()
            connection.close()
        except Exception as e:
            self.user_info_label.setText(f"Ошибка загрузки данных: {e}")

    def clear_content_layout(self):
        clear_layout(self.content_layout)

    def show_admin_panel(self):
        self.clear_content_layout()
        admin_layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        add_user_btn = QPushButton("Добавить пользователя")
        add_user_btn.clicked.connect(self.open_add_user_window)
        button_layout.addWidget(add_user_btn)

        unblock_btn = QPushButton("Снять блокировку")
        unblock_btn.clicked.connect(self.unblock_user)
        button_layout.addWidget(unblock_btn)

        block_btn = QPushButton("Заблокировать")
        block_btn.clicked.connect(self.block_user)
        button_layout.addWidget(block_btn)
        admin_layout.addLayout(button_layout)

        info_label = QLabel("Админ: здесь можно редактировать пользователей")
        info_label.setAlignment(Qt.AlignCenter)
        admin_layout.addWidget(info_label)

        self.content_layout.addLayout(admin_layout)

    def open_add_user_window(self):
        self.add_user_window = AdminAddUserWindow()
        self.add_user_window.show()

    def unblock_user(self):
        login, ok = QInputDialog.getText(self, "Разблокировка", "Введите логин пользователя:")
        if ok and login:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("UPDATE Users SET block = 0, failed_attempts = 0 WHERE user_login = %s", (login,))
                if cursor.rowcount == 0:
                    QMessageBox.warning(self, "Ошибка", "Пользователь не найден")
                else:
                    connection.commit()
                    QMessageBox.information(self, "Успех", "Пользователь разблокирован")
                cursor.close()
                connection.close()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка разблокировки: {e}")

    def block_user(self):
        login, ok = QInputDialog.getText(self, "Блокировка", "Введите логин пользователя для блокировки:")
        if ok and login:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("UPDATE Users SET block = 1 WHERE user_login = %s", (login,))
                if cursor.rowcount == 0:
                    QMessageBox.warning(self, "Ошибка", "Пользователь не найден")
                else:
                    connection.commit()
                    QMessageBox.information(self, "Успех", "Пользователь заблокирован")
                cursor.close()
                connection.close()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка блокировки: {e}")

    def show_manager_panel(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Управление персоналом (Менеджер)")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        staff_button = QPushButton("Список персонала")
        staff_button.clicked.connect(self.show_staff_list)
        layout.addWidget(staff_button)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.display_user_info)
        layout.addWidget(back_button)

        self.content_layout.addLayout(layout)

    def show_staff_list(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Список персонала")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT u.first_name, u.last_name, u.email, p.position_name
                FROM Users u
                JOIN Position p ON u.position_id = p.position_id
                WHERE LOWER(p.position_name) = 'персонал'
            """)
            staff = cursor.fetchall()
            cursor.close()
            connection.close()
            if staff:
                for person in staff:
                    f_name, l_name, mail, pos_name = person
                    lbl = QLabel(f"{f_name} {l_name} ({mail}) - {pos_name}")
                    layout.addWidget(lbl)
            else:
                layout.addWidget(QLabel("Персонал не найден."))
        except Exception as e:
            layout.addWidget(QLabel(f"Ошибка: {e}"))
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.show_manager_panel)
        layout.addWidget(back_button)
        self.content_layout.addLayout(layout)

    def show_user_panel(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Заказ услуг (Пользователь)")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        order_button = QPushButton("Заказать услугу")
        order_button.clicked.connect(self.order_service)
        layout.addWidget(order_button)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.display_user_info)
        layout.addWidget(back_button)
        self.content_layout.addLayout(layout)

    def order_service(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Оформление заказа")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(QLabel("Тут будет форма заказа услуг."))
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.show_user_panel)
        layout.addWidget(back_button)
        self.content_layout.addLayout(layout)

    def show_staff_panel(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Расписание (Персонал)")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        schedule_button = QPushButton("Моё расписание")
        schedule_button.clicked.connect(self.show_schedule)
        layout.addWidget(schedule_button)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.display_user_info)
        layout.addWidget(back_button)
        self.content_layout.addLayout(layout)

    def show_schedule(self):
        self.clear_content_layout()
        layout = QVBoxLayout()
        title = QLabel("Ваше расписание")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT work_date, shift_start, shift_end
                FROM StaffSchedule
                WHERE user_id = %s
                ORDER BY work_date
            """, (self.user_id,))
            schedule_rows = cursor.fetchall()
            cursor.close()
            connection.close()
            if schedule_rows:
                for row in schedule_rows:
                    work_date, shift_start, shift_end = row
                    lbl = QLabel(f"Дата: {work_date}, смена: {shift_start} - {shift_end}")
                    layout.addWidget(lbl)
            else:
                layout.addWidget(QLabel("Расписание не найдено."))
        except Exception as e:
            layout.addWidget(QLabel(f"Ошибка: {e}"))
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.show_staff_panel)
        layout.addWidget(back_button)
        self.content_layout.addLayout(layout)

    def show_change_password_form(self):
        self.clear_content_layout()
        form_layout = QVBoxLayout()
        title = QLabel("Изменить пароль")
        title.setAlignment(Qt.AlignCenter)
        form_layout.addWidget(title)

        self.current_password = QLineEdit()
        self.current_password.setPlaceholderText("Текущий пароль")
        self.current_password.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.current_password)

        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Новый пароль")
        self.new_password.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.new_password)

        self.repeat_password = QLineEdit()
        self.repeat_password.setPlaceholderText("Подтвердите новый пароль")
        self.repeat_password.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.repeat_password)

        change_button = QPushButton("Изменить пароль")
        change_button.clicked.connect(self.change_password)
        form_layout.addWidget(change_button)

        self.pass_message = QLabel("")
        self.pass_message.setAlignment(Qt.AlignCenter)
        form_layout.addWidget(self.pass_message)

        self.content_layout.addLayout(form_layout)

    def change_password(self):
        current = self.current_password.text().strip()
        new = self.new_password.text().strip()
        repeat = self.repeat_password.text().strip()
        if not current or not new or not repeat:
            self.pass_message.setText("Все поля обязательны для заполнения")
            return
        if new != repeat:
            self.pass_message.setText("Новые пароли не совпадают")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT user_password FROM Users WHERE user_id = %s", (self.user_id,))
            db_current = cursor.fetchone()[0]
            if current != db_current:
                self.pass_message.setText("Неверный текущий пароль")
                cursor.close()
                connection.close()
                return
            cursor.execute("UPDATE Users SET user_password = %s WHERE user_id = %s", (new, self.user_id))
            connection.commit()
            self.pass_message.setStyleSheet("color: green;")
            self.pass_message.setText("Пароль успешно изменён")
            cursor.close()
            connection.close()
        except Exception as e:
            self.pass_message.setText(f"Ошибка: {e}")


class AdminAddUserWindow(QWidget):
    """Окно добавления пользователя (только для администратора)."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Добавить пользователя")
        self.resize(400, 400)
        self.center()
        self.init_ui()

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.frameGeometry()
        self.move(
            screen.center().x() - size.width() // 2,
            screen.center().y() - size.height() // 2
        )

    def init_ui(self):
        layout = QFormLayout()
        self.first_name_input = QLineEdit()
        layout.addRow("Имя:", self.first_name_input)

        self.last_name_input = QLineEdit()
        layout.addRow("Фамилия:", self.last_name_input)

        self.phone_input = QLineEdit()
        layout.addRow("Телефон:", self.phone_input)

        self.email_input = QLineEdit()
        layout.addRow("Email:", self.email_input)

        self.login_input = QLineEdit()
        layout.addRow("Логин:", self.login_input)

        self.position_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT position_id, position_name FROM Position")
            positions = cursor.fetchall()
            for pos in positions:
                self.position_combo.addItem(pos[1], pos[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки должностей: {e}")
        layout.addRow("Должность:", self.position_combo)

        self.add_btn = QPushButton("Добавить пользователя")
        self.add_btn.clicked.connect(self.add_user)
        layout.addWidget(self.add_btn)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addRow(self.message_label)

        self.setLayout(layout)

    def add_user(self):
        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        user_login = self.login_input.text().strip()
        position_id = self.position_combo.currentData()

        user_password = DEFAULT_PASSWORD

        if not (first_name and last_name and phone and email and user_login):
            self.message_label.setText("Все поля обязательны для заполнения")
            return

        if not phone.isdigit():
            self.message_label.setText("Телефон должен содержать только цифры")
            return

        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Users 
                    (first_name, last_name, phone, email, user_login, user_password, position_id, created_at, block, failed_attempts)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
            """
            now = datetime.now()
            cursor.execute(query, (first_name, last_name, phone, email, user_login, user_password, position_id, now))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Пользователь успешно добавлен")
        except psycopg2.Error as e:
            error_message = str(e)
            if "users_phone_key" in error_message:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Ошибка: телефон уже используется")
            elif "users_login_key" in error_message:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Ошибка: логин уже существует")
            else:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText(f"Ошибка: {error_message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec())
#stable