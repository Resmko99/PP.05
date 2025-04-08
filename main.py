import sys
import psycopg2
from datetime import datetime, timedelta, date

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QMessageBox, QInputDialog, QComboBox, QFormLayout,
    QStackedWidget, QScrollArea, QDialog, QTableWidget, QTableWidgetItem,
    QFileDialog, QDateEdit
)
from PySide6.QtCore import Qt, QTimer, QDate
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
    """Рекурсивное удаление всех элементов компоновки."""
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                clear_layout(item.layout())

# ================== Окно авторизации ==================
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
            # Если пользователь заблокирован, выводим сообщение
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
                    self.error_label.setText("Вы заблокированы из-за повторных неудач. Обратитесь к администратору")
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

# ================== Окно смены пароля ==================
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

# ================== Главное окно ==================
class MainWindow(QWidget):
    def __init__(self, user_id, position_id):
        super().__init__()
        self.user_id = user_id
        self.position_id = position_id
        self.setWindowTitle("Главное Отеля Хазбра")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)
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
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.menu_layout = QVBoxLayout()
        self.menu_layout.setSpacing(10)
        btn_admin = QPushButton("Админ")
        btn_admin.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.menu_layout.addWidget(btn_admin)
        btn_clients = QPushButton("Клиенты")
        btn_clients.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.menu_layout.addWidget(btn_clients)
        btn_rooms = QPushButton("Номера")
        btn_rooms.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.menu_layout.addWidget(btn_rooms)
        btn_bookings = QPushButton("Бронирования")
        btn_bookings.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
        self.menu_layout.addWidget(btn_bookings)
        btn_payments = QPushButton("Платежи")
        btn_payments.clicked.connect(lambda: self.content_stack.setCurrentIndex(4))
        self.menu_layout.addWidget(btn_payments)
        btn_services = QPushButton("Доп. услуги")
        btn_services.clicked.connect(lambda: self.content_stack.setCurrentIndex(5))
        self.menu_layout.addWidget(btn_services)
        btn_documents = QPushButton("Документы")
        btn_documents.clicked.connect(lambda: self.content_stack.setCurrentIndex(6))
        self.menu_layout.addWidget(btn_documents)
        self.menu_layout.addStretch()

        self.content_stack = QStackedWidget()
        self.page_admin = AdminUsersPanel()            # Панель админа
        self.page_clients = ClientsPanel()              # Панель клиентов
        self.page_rooms = RoomsPanel()                  # Панель номеров
        self.page_bookings = BookingsPanel()            # Панель бронирований
        self.page_payments = PaymentsPanel()            # Панель платежей
        self.page_services = ServicesPanel()            # Панель доп. услуг
        self.page_documents = DocumentsPanel()          # Панель документов

        self.content_stack.addWidget(self.page_admin)    # индекс 0
        self.content_stack.addWidget(self.page_clients)  # индекс 1
        self.content_stack.addWidget(self.page_rooms)    # индекс 2
        self.content_stack.addWidget(self.page_bookings) # индекс 3
        self.content_stack.addWidget(self.page_payments) # индекс 4
        self.content_stack.addWidget(self.page_services) # индекс 5
        self.content_stack.addWidget(self.page_documents) # индекс 6

        main_layout.addLayout(self.menu_layout, 1)
        main_layout.addWidget(self.content_stack, 4)

        top_layout = QHBoxLayout()
        self.user_info_label = QLabel("")
        top_layout.addWidget(self.user_info_label)
        top_layout.addStretch()
        self.minimize_button = QPushButton("-")
        self.minimize_button.setFixedSize(40, 30)
        self.minimize_button.clicked.connect(self.showMinimized)
        top_layout.addWidget(self.minimize_button)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(40, 30)
        self.close_button.clicked.connect(self.close)
        top_layout.addWidget(self.close_button)

        outer_layout = QVBoxLayout()
        outer_layout.addLayout(top_layout)
        outer_layout.addLayout(main_layout)
        self.setLayout(outer_layout)
        self.load_user_info()

    def load_user_info(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT first_name, last_name, email, position_id FROM Users WHERE user_id = %s", (self.user_id,))
            user = cursor.fetchone()
            if user:
                first_name, last_name, email, pos_id = user
                if not self.position_id:
                    self.position_id = pos_id
                cursor.execute("SELECT position_name FROM Position WHERE position_id = %s", (self.position_id,))
                pos = cursor.fetchone()
                pos_name = pos[0] if pos else ""
                self.user_info_label.setText(f"{pos_name}: {first_name} {last_name} ({email})")
            cursor.close()
            connection.close()
        except Exception as e:
            self.user_info_label.setText(f"Ошибка загрузки данных: {e}")

# ================== Панель управления пользователями ==================
class AdminUsersPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_user_id = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Управление пользователями")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Имя", "Фамилия", "Логин", "Email", "Статус"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_change)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить пользователя")
        self.add_btn.clicked.connect(self.add_user)
        btn_layout.addWidget(self.add_btn)

        self.toggle_btn = QPushButton("Блокировать/Разблокировать")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_block)
        btn_layout.addWidget(self.toggle_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_data()

    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, first_name, last_name, user_login, email, block 
                FROM Users ORDER BY user_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                user_id, first_name, last_name, user_login, email, block = row
                self.table.setItem(i, 0, QTableWidgetItem(str(user_id)))
                self.table.setItem(i, 1, QTableWidgetItem(first_name))
                self.table.setItem(i, 2, QTableWidgetItem(last_name))
                self.table.setItem(i, 3, QTableWidgetItem(user_login))
                self.table.setItem(i, 4, QTableWidgetItem(email))
                status_item = QTableWidgetItem("Заблокирован" if block == 1 else "Активен")
                self.table.setItem(i, 5, status_item)
                if block == 1:
                    for col in range(self.table.columnCount()):
                        self.table.item(i, col).setBackground(Qt.red)
            cursor.close()
            connection.close()
            self.selected_user_id = None
            self.toggle_btn.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки пользователей: {e}")

    def on_selection_change(self):
        selected_items = self.table.selectedItems()
        if selected_items:
            self.selected_user_id = int(selected_items[0].text())
            status = selected_items[5].text()
            if status == "Заблокирован":
                self.toggle_btn.setText("Разблокировать")
            else:
                self.toggle_btn.setText("Заблокировать")
            self.toggle_btn.setEnabled(True)
        else:
            self.selected_user_id = None
            self.toggle_btn.setEnabled(False)

    def toggle_block(self):
        if self.selected_user_id is None:
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT block FROM Users WHERE user_id = %s", (self.selected_user_id,))
            result = cursor.fetchone()
            if not result:
                QMessageBox.warning(self, "Ошибка", "Пользователь не найден")
                return
            current_block = result[0]
            if current_block == 1:
                cursor.execute("UPDATE Users SET block = 0, failed_attempts = 0 WHERE user_id = %s", (self.selected_user_id,))
            else:
                cursor.execute("UPDATE Users SET block = 1 WHERE user_id = %s", (self.selected_user_id,))
            connection.commit()
            cursor.close()
            connection.close()
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления статуса: {e}")

    def add_user(self):
        dialog = AddUserDialog(self)
        if dialog.exec():
            self.load_data()

# ================== Диалог добавления пользователя ==================
class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить пользователя")
        self.resize(400, 400)
        self.init_ui()

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
            self.message_label.setText("Все поля обязательны")
            return
        if phone == "1" or email == "1":
            self.message_label.setText("Недопустимое значение для телефона или email")
            return
        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё]+", first_name):
            self.message_label.setText("Имя должно содержать только буквы")
            return
        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё]+", last_name):
            self.message_label.setText("Фамилия должна содержать только буквы")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Users 
                    (first_name, last_name, phone, email, user_login, user_password, position_id, created_at)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (first_name, last_name, phone, email, user_login, user_password, position_id, now))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Пользователь добавлен")
            QTimer.singleShot(1500, self.accept)
        except psycopg2.Error as e:
            error_message = str(e)
            if "users_phone_key" in error_message:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Телефон уже используется")
            elif "users_login_key" in error_message:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Логин уже существует")
            else:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText(f"Ошибка: {error_message}")

# ================== Панель для Клиентов ==================
class ClientsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить клиента")
        add_btn.clicked.connect(self.add_client)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать клиента")
        edit_btn.clicked.connect(self.edit_client)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить клиента")
        delete_btn.clicked.connect(self.delete_client)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT client_id, first_name, last_name, phone, email, registered_at FROM Clients ORDER BY client_id")
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(6)
            self.table.setHorizontalHeaderLabels(["ID", "Имя", "Фамилия", "Телефон", "Email", "Дата регистрации"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки клиентов: {e}")
    def add_client(self):
        dialog = AddClientDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_client(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите клиента для редактирования")
            return
        client_id_item = self.table.item(row, 0)
        if client_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор клиента")
            return
        try:
            client_id = int(client_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать client_id: {e}")
            return
        dialog = EditClientDialog(client_id, self)
        if dialog.exec():
            self.load_data()
    def delete_client(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите клиента для удаления")
            return
        client_id_item = self.table.item(row, 0)
        if client_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор клиента")
            return
        try:
            client_id = int(client_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать client_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранного клиента?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM Clients WHERE client_id = %s", (client_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления клиента: {e}")

class AddClientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить клиента")
        self.resize(400, 300)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.first_name = QLineEdit()
        layout.addRow("Имя:", self.first_name)
        self.last_name = QLineEdit()
        layout.addRow("Фамилия:", self.last_name)
        self.phone = QLineEdit()
        layout.addRow("Телефон:", self.phone)
        self.email = QLineEdit()
        layout.addRow("Email:", self.email)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_client)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def add_client(self):
        first_name = self.first_name.text().strip()
        last_name = self.last_name.text().strip()
        phone = self.phone.text().strip()
        email = self.email.text().strip()
        if not (first_name and last_name and phone and email):
            self.message_label.setText("Все поля обязательны")
            return
        if phone == "1" or email == "1":
            self.message_label.setText("Недопустимое значение для телефона или email")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Clients (first_name, last_name, phone, email, registered_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (first_name, last_name, phone, email, now))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Клиент добавлен")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

class EditClientDialog(QDialog):
    def __init__(self, client_id, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.setWindowTitle("Редактировать клиента")
        self.resize(400, 300)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.first_name = QLineEdit()
        layout.addRow("Имя:", self.first_name)
        self.last_name = QLineEdit()
        layout.addRow("Фамилия:", self.last_name)
        self.phone = QLineEdit()
        layout.addRow("Телефон:", self.phone)
        self.email = QLineEdit()
        layout.addRow("Email:", self.email)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_client)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT first_name, last_name, phone, email FROM Clients WHERE client_id = %s", (self.client_id,))
            data = cursor.fetchone()
            if data:
                self.first_name.setText(data[0])
                self.last_name.setText(data[1])
                self.phone.setText(data[2])
                self.email.setText(data[3])
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_client(self):
        first_name = self.first_name.text().strip()
        last_name = self.last_name.text().strip()
        phone = self.phone.text().strip()
        email = self.email.text().strip()
        if not (first_name and last_name and phone and email):
            self.message_label.setText("Все поля обязательны")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE Clients SET first_name = %s, last_name = %s, phone = %s, email = %s
                WHERE client_id = %s
            """, (first_name, last_name, phone, email, self.client_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Клиент обновлён")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# ================== Панель для Номеров ==================
class RoomsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить номер")
        add_btn.clicked.connect(self.add_room)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать номер")
        edit_btn.clicked.connect(self.edit_room)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить номер")
        delete_btn.clicked.connect(self.delete_room)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT room_id, room_number, floor, capacity, category_id 
                FROM Rooms ORDER BY room_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Номер", "Этаж", "Вместимость", "Категория"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки номеров: {e}")
    def add_room(self):
        dialog = AddRoomDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_room(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите номер для редактирования")
            return
        room_id_item = self.table.item(row, 0)
        if room_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор номера")
            return
        try:
            room_id = int(room_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать room_id: {e}")
            return
        dialog = EditRoomDialog(room_id, self)
        if dialog.exec():
            self.load_data()
    def delete_room(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите номер для удаления")
            return
        room_id_item = self.table.item(row, 0)
        if room_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор номера")
            return
        try:
            room_id = int(room_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать room_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранный номер?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM Rooms WHERE room_id = %s", (room_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления номера: {e}")

class AddRoomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить номер")
        self.resize(400, 300)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.room_number = QLineEdit()
        layout.addRow("Номер:", self.room_number)
        self.floor = QLineEdit()
        layout.addRow("Этаж:", self.floor)
        self.capacity = QLineEdit()
        layout.addRow("Вместимость:", self.capacity)
        self.category_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT category_id, category_name FROM Category")
            categories = cursor.fetchall()
            for cat in categories:
                self.category_combo.addItem(cat[1], cat[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки категорий: {e}")
        layout.addRow("Категория:", self.category_combo)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_room)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def add_room(self):
        room_number = self.room_number.text().strip()
        floor = self.floor.text().strip()
        capacity = self.capacity.text().strip()
        category_id = self.category_combo.currentData()
        if not (room_number and floor and capacity):
            self.message_label.setText("Все поля обязательны")
            return
        try:
            floor = int(floor)
            capacity = int(capacity)
        except ValueError:
            self.message_label.setText("Этаж и вместимость должны быть числами")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Rooms (room_number, floor, capacity, category_id)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (room_number, floor, capacity, category_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Номер добавлен")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

class EditRoomDialog(QDialog):
    def __init__(self, room_id, parent=None):
        super().__init__(parent)
        self.room_id = room_id
        self.setWindowTitle("Редактировать номер")
        self.resize(400, 300)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.room_number = QLineEdit()
        layout.addRow("Номер:", self.room_number)
        self.floor = QLineEdit()
        layout.addRow("Этаж:", self.floor)
        self.capacity = QLineEdit()
        layout.addRow("Вместимость:", self.capacity)
        self.category_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT category_id, category_name FROM Category")
            categories = cursor.fetchall()
            for cat in categories:
                self.category_combo.addItem(cat[1], cat[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки категорий: {e}")
        layout.addRow("Категория:", self.category_combo)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_room)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT room_number, floor, capacity, category_id FROM Rooms WHERE room_id = %s", (self.room_id,))
            data = cursor.fetchone()
            if data:
                self.room_number.setText(data[0])
                self.floor.setText(str(data[1]))
                self.capacity.setText(str(data[2]))
                index = self.category_combo.findData(data[3])
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_room(self):
        room_number = self.room_number.text().strip()
        floor = self.floor.text().strip()
        capacity = self.capacity.text().strip()
        category_id = self.category_combo.currentData()
        if not (room_number and floor and capacity):
            self.message_label.setText("Все поля обязательны")
            return
        try:
            floor = int(floor)
            capacity = int(capacity)
        except ValueError:
            self.message_label.setText("Этаж и вместимость должны быть числами")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE Rooms SET room_number = %s, floor = %s, capacity = %s, category_id = %s
                WHERE room_id = %s
            """, (room_number, floor, capacity, category_id, self.room_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Номер обновлён")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# ================== Панель для Бронирований ==================
# Здесь добавлены выбор даты через QDateEdit, выбор номера и проверка пересечения дат
class BookingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить бронирование")
        add_btn.clicked.connect(self.add_booking)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать бронирование")
        edit_btn.clicked.connect(self.edit_booking)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить бронирование")
        delete_btn.clicked.connect(self.delete_booking)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT booking_id, client_id, user_id, booking_date, arrival_date, departure_date, booking_status_id, total_cost 
                FROM Bookings ORDER BY booking_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels(["ID", "Клиент", "Пользователь", "Дата бронир.", "Прибытие", "Выезд", "Статус", "Стоимость"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    display_value = "" if value is None else str(value)
                    self.table.setItem(i, j, QTableWidgetItem(display_value))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
    def add_booking(self):
        dialog = AddBookingDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_booking(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите бронирование для редактирования")
            return
        booking_id_item = self.table.item(row, 0)
        if booking_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор бронирования")
            return
        try:
            booking_id = int(booking_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать booking_id: {e}")
            return
        dialog = EditBookingDialog(booking_id, self)
        if dialog.exec():
            self.load_data()
    def delete_booking(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите бронирование для удаления")
            return
        booking_id_item = self.table.item(row, 0)
        if booking_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор бронирования")
            return
        try:
            booking_id = int(booking_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать booking_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранное бронирование?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM Bookings WHERE booking_id = %s", (booking_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления бронирования: {e}")

# Диалог добавления бронирования с выбором даты и номера
class AddBookingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить бронирование")
        self.resize(400, 450)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.client_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT client_id, first_name, last_name FROM Clients")
            for row in cursor.fetchall():
                self.client_combo.addItem(f"{row[1]} {row[2]}", row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки клиентов: {e}")
        layout.addRow("Клиент:", self.client_combo)
        # Выбор дат с календарём
        self.arrival_date = QDateEdit(calendarPopup=True)
        self.arrival_date.setDisplayFormat("yyyy-MM-dd")
        self.arrival_date.setDate(QDate.currentDate())
        layout.addRow("Заезд:", self.arrival_date)
        self.departure_date = QDateEdit(calendarPopup=True)
        self.departure_date.setDisplayFormat("yyyy-MM-dd")
        self.departure_date.setDate(QDate.currentDate().addDays(1))
        layout.addRow("Выезд:", self.departure_date)
        # Выбор статуса бронирования
        self.status_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_status_id, status_name FROM BookingStatus")
            for row in cursor.fetchall():
                self.status_combo.addItem(row[1], row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки статусов: {e}")
        layout.addRow("Статус:", self.status_combo)
        self.total_cost = QLineEdit()
        layout.addRow("Стоимость:", self.total_cost)
        # Выбор номера комнаты
        self.room_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT room_id, room_number FROM Rooms ORDER BY room_number")
            for row in cursor.fetchall():
                self.room_combo.addItem(f"Номер: {row[1]}", row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки номеров: {e}")
        layout.addRow("Комната:", self.room_combo)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_booking)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def add_booking(self):
        client_id = self.client_combo.currentData()
        arrival = self.arrival_date.date().toPython()
        departure = self.departure_date.date().toPython()
        if departure <= arrival:
            self.message_label.setText("Дата выезда должна быть позже даты заезда")
            return
        status_id = self.status_combo.currentData()
        try:
            total_cost = float(self.total_cost.text().strip())
        except Exception:
            self.message_label.setText("Стоимость должна быть числом")
            return
        room_id = self.room_combo.currentData()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT b.booking_date 
                FROM BookingRooms br
                JOIN Bookings b ON br.booking_id = b.booking_id
                WHERE br.room_id = %s
                  AND NOT ( %s <= b.arrival_date OR %s >= (b.departure_date + INTERVAL '1 day'))
            """, (room_id, departure, arrival))
            conflict = cursor.fetchone()
            if conflict:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Выбранный номер занят на эти даты.")
                cursor.close()
                connection.close()
                return
            now = datetime.now()
            cursor.execute("""
                INSERT INTO Bookings (client_id, booking_date, arrival_date, departure_date, booking_status_id, total_cost)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING booking_id
            """, (client_id, now, arrival, departure, status_id, total_cost))
            booking_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO BookingRooms (booking_id, room_id)
                VALUES (%s, %s)
            """, (booking_id, room_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Бронирование добавлено")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# Диалог редактирования бронирования (аналогично с выбором номера и дат)
class EditBookingDialog(QDialog):
    def __init__(self, booking_id, parent=None):
        super().__init__(parent)
        self.booking_id = booking_id
        self.setWindowTitle("Редактировать бронирование")
        self.resize(400, 450)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.client_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT client_id, first_name, last_name FROM Clients")
            for row in cursor.fetchall():
                self.client_combo.addItem(f"{row[1]} {row[2]}", row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки клиентов: {e}")
        layout.addRow("Клиент:", self.client_combo)
        self.arrival_date = QDateEdit(calendarPopup=True)
        self.arrival_date.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Заезд:", self.arrival_date)
        self.departure_date = QDateEdit(calendarPopup=True)
        self.departure_date.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Выезд:", self.departure_date)
        self.status_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_status_id, status_name FROM BookingStatus")
            for row in cursor.fetchall():
                self.status_combo.addItem(row[1], row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки статусов: {e}")
        layout.addRow("Статус:", self.status_combo)
        self.total_cost = QLineEdit()
        layout.addRow("Стоимость:", self.total_cost)
        self.room_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT room_id, room_number FROM Rooms ORDER BY room_number")
            for row in cursor.fetchall():
                self.room_combo.addItem(f"Номер: {row[1]}", row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки номеров: {e}")
        layout.addRow("Комната:", self.room_combo)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_booking)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT client_id, arrival_date, departure_date, booking_status_id, total_cost 
                FROM Bookings WHERE booking_id = %s
            """, (self.booking_id,))
            data = cursor.fetchone()
            if data:
                client_id, arrival, departure, status_id, total_cost = data
                index = self.client_combo.findData(client_id)
                if index >= 0:
                    self.client_combo.setCurrentIndex(index)
                self.arrival_date.setDate(QDate(arrival.year, arrival.month, arrival.day))
                self.departure_date.setDate(QDate(departure.year, departure.month, departure.day))
                index = self.status_combo.findData(status_id)
                if index >= 0:
                    self.status_combo.setCurrentIndex(index)
                self.total_cost.setText(str(total_cost))
            cursor.execute("SELECT room_id FROM BookingRooms WHERE booking_id = %s", (self.booking_id,))
            room = cursor.fetchone()
            if room:
                room_id = room[0]
                index = self.room_combo.findData(room_id)
                if index >= 0:
                    self.room_combo.setCurrentIndex(index)
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_booking(self):
        client_id = self.client_combo.currentData()
        arrival = self.arrival_date.date().toPython()
        departure = self.departure_date.date().toPython()
        if departure <= arrival:
            self.message_label.setText("Дата выезда должна быть позже даты заезда")
            return
        status_id = self.status_combo.currentData()
        try:
            total_cost = float(self.total_cost.text().strip())
        except Exception:
            self.message_label.setText("Стоимость должна быть числом")
            return
        room_id = self.room_combo.currentData()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            # Проверка занятости, исключая текущее бронирование
            cursor.execute("""
                SELECT b.booking_id
                FROM BookingRooms br
                JOIN Bookings b ON br.booking_id = b.booking_id
                WHERE br.room_id = %s
                  AND b.booking_id <> %s
                  AND NOT ( %s <= b.arrival_date OR %s >= (b.departure_date + INTERVAL '1 day'))
            """, (room_id, self.booking_id, departure, arrival))
            conflict = cursor.fetchone()
            if conflict:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("Выбранный номер занят на эти даты")
                cursor.close()
                connection.close()
                return
            cursor.execute("""
                UPDATE Bookings SET client_id = %s, arrival_date = %s, departure_date = %s, booking_status_id = %s, total_cost = %s
                WHERE booking_id = %s
            """, (client_id, arrival, departure, status_id, total_cost, self.booking_id))
            cursor.execute("DELETE FROM BookingRooms WHERE booking_id = %s", (self.booking_id,))
            cursor.execute("INSERT INTO BookingRooms (booking_id, room_id) VALUES (%s, %s)", (self.booking_id, room_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Бронирование обновлено")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# ================== Панель для Платежей ==================
class PaymentsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить платеж")
        add_btn.clicked.connect(self.add_payment)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать платеж")
        edit_btn.clicked.connect(self.edit_payment)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить платеж")
        delete_btn.clicked.connect(self.delete_payment)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT payment_id, booking_id, payment_date, amount, payment_method_id 
                FROM Payments ORDER BY payment_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Бронирование", "Дата платежа", "Сумма", "Способ оплаты"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки платежей: {e}")
    def add_payment(self):
        dialog = AddPaymentDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_payment(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите платеж для редактирования")
            return
        payment_id_item = self.table.item(row, 0)
        if payment_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор платежа")
            return
        try:
            payment_id = int(payment_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать payment_id: {e}")
            return
        dialog = EditPaymentDialog(payment_id, self)
        if dialog.exec():
            self.load_data()
    def delete_payment(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите платеж для удаления")
            return
        payment_id_item = self.table.item(row, 0)
        if payment_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор платежа")
            return
        try:
            payment_id = int(payment_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать payment_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранный платеж?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM Payments WHERE payment_id = %s", (payment_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления платежа: {e}")

class AddPaymentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить платеж")
        self.resize(400, 300)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.booking_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_id FROM Bookings")
            for row in cursor.fetchall():
                self.booking_combo.addItem(str(row[0]), row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
        layout.addRow("Бронирование:", self.booking_combo)
        self.amount = QLineEdit()
        layout.addRow("Сумма:", self.amount)
        self.method_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT payment_method_id, method_name FROM PaymentMethod")
            for row in cursor.fetchall():
                self.method_combo.addItem(row[1], row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки способов оплаты: {e}")
        layout.addRow("Способ оплаты:", self.method_combo)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_payment)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def add_payment(self):
        booking_id = self.booking_combo.currentData()
        try:
            amount = float(self.amount.text().strip())
        except Exception:
            self.message_label.setText("Сумма должна быть числом")
            return
        method_id = self.method_combo.currentData()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Payments (booking_id, payment_date, amount, payment_method_id)
                VALUES (%s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (booking_id, now, amount, method_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Платеж добавлен")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

class EditPaymentDialog(QDialog):
    def __init__(self, payment_id, parent=None):
        super().__init__(parent)
        self.payment_id = payment_id
        self.setWindowTitle("Редактировать платеж")
        self.resize(400, 300)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.booking_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_id FROM Bookings")
            for row in cursor.fetchall():
                self.booking_combo.addItem(str(row[0]), row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
        layout.addRow("Бронирование:", self.booking_combo)
        self.amount = QLineEdit()
        layout.addRow("Сумма:", self.amount)
        self.method_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT payment_method_id, method_name FROM PaymentMethod")
            for row in cursor.fetchall():
                self.method_combo.addItem(row[1], row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки способов оплаты: {e}")
        layout.addRow("Способ оплаты:", self.method_combo)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_payment)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT booking_id, amount, payment_method_id FROM Payments WHERE payment_id = %s
            """, (self.payment_id,))
            data = cursor.fetchone()
            if data:
                booking_id, amount, method_id = data
                index = self.booking_combo.findData(booking_id)
                if index >= 0:
                    self.booking_combo.setCurrentIndex(index)
                self.amount.setText(str(amount))
                index = self.method_combo.findData(method_id)
                if index >= 0:
                    self.method_combo.setCurrentIndex(index)
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_payment(self):
        booking_id = self.booking_combo.currentData()
        try:
            amount = float(self.amount.text().strip())
        except Exception:
            self.message_label.setText("Сумма должна быть числом")
            return
        method_id = self.method_combo.currentData()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE Payments SET booking_id = %s, amount = %s, payment_method_id = %s
                WHERE payment_id = %s
            """, (booking_id, amount, method_id, self.payment_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Платеж обновлён")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# ================== Панель для Дополнительных услуг ==================
class ServicesPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить услугу")
        add_btn.clicked.connect(self.add_service)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать услугу")
        edit_btn.clicked.connect(self.edit_service)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить услугу")
        delete_btn.clicked.connect(self.delete_service)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT service_id, service_name, price, description 
                FROM AdditionalServices ORDER BY service_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["ID", "Название", "Цена", "Описание"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки услуг: {e}")
    def add_service(self):
        dialog = AddServiceDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_service(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите услугу для редактирования")
            return
        service_id_item = self.table.item(row, 0)
        if service_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор услуги")
            return
        try:
            service_id = int(service_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать service_id: {e}")
            return
        dialog = EditServiceDialog(service_id, self)
        if dialog.exec():
            self.load_data()
    def delete_service(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите услугу для удаления")
            return
        service_id_item = self.table.item(row, 0)
        if service_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор услуги")
            return
        try:
            service_id = int(service_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать service_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранную услугу?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM AdditionalServices WHERE service_id = %s", (service_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления услуги: {e}")

class AddServiceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить услугу")
        self.resize(400, 300)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.service_name = QLineEdit()
        layout.addRow("Название:", self.service_name)
        self.price = QLineEdit()
        layout.addRow("Цена:", self.price)
        self.description = QLineEdit()
        layout.addRow("Описание:", self.description)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_service)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def add_service(self):
        service_name = self.service_name.text().strip()
        try:
            price = float(self.price.text().strip())
        except Exception:
            self.message_label.setText("Цена должна быть числом")
            return
        description = self.description.text().strip()
        if not service_name:
            self.message_label.setText("Название обязательно")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO AdditionalServices (service_name, price, description)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (service_name, price, description))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Услуга добавлена")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

class EditServiceDialog(QDialog):
    def __init__(self, service_id, parent=None):
        super().__init__(parent)
        self.service_id = service_id
        self.setWindowTitle("Редактировать услугу")
        self.resize(400, 300)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.service_name = QLineEdit()
        layout.addRow("Название:", self.service_name)
        self.price = QLineEdit()
        layout.addRow("Цена:", self.price)
        self.description = QLineEdit()
        layout.addRow("Описание:", self.description)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_service)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT service_name, price, description FROM AdditionalServices WHERE service_id = %s", (self.service_id,))
            data = cursor.fetchone()
            if data:
                self.service_name.setText(data[0])
                self.price.setText(str(data[1]))
                self.description.setText(data[2] if data[2] else "")
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_service(self):
        service_name = self.service_name.text().strip()
        try:
            price = float(self.price.text().strip())
        except Exception:
            self.message_label.setText("Цена должна быть числом")
            return
        description = self.description.text().strip()
        if not service_name:
            self.message_label.setText("Название обязательно")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE AdditionalServices SET service_name = %s, price = %s, description = %s
                WHERE service_id = %s
            """, (service_name, price, description, self.service_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Услуга обновлена")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

# ================== Панель для Документов ==================
class DocumentsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить документ")
        add_btn.clicked.connect(self.add_document)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать документ")
        edit_btn.clicked.connect(self.edit_document)
        btn_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Удалить документ")
        delete_btn.clicked.connect(self.delete_document)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_data()
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT document_id, booking_id, doc_name, doc_path, doc_create_date 
                FROM Documents ORDER BY document_id
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Бронирование", "Название", "Путь", "Дата создания"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки документов: {e}")
    def add_document(self):
        dialog = AddDocumentDialog(self)
        if dialog.exec():
            self.load_data()
    def edit_document(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите документ для редактирования")
            return
        document_id_item = self.table.item(row, 0)
        if document_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор документа")
            return
        try:
            document_id = int(document_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать document_id: {e}")
            return
        dialog = EditDocumentDialog(document_id, self)
        if dialog.exec():
            self.load_data()
    def delete_document(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите документ для удаления")
            return
        document_id_item = self.table.item(row, 0)
        if document_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить идентификатор документа")
            return
        try:
            document_id = int(document_id_item.text())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Невозможно конвертировать document_id: {e}")
            return
        reply = QMessageBox.question(self, "Подтверждение", "Удалить выбранный документ?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                connection = db_connect()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM Documents WHERE document_id = %s", (document_id,))
                connection.commit()
                cursor.close()
                connection.close()
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления документа: {e}")

class AddDocumentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить документ")
        self.resize(400, 300)
        self.init_ui()
    def init_ui(self):
        layout = QFormLayout()
        self.booking_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_id FROM Bookings")
            for row in cursor.fetchall():
                self.booking_combo.addItem(str(row[0]), row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
        layout.addRow("Бронирование:", self.booking_combo)
        self.doc_name = QLineEdit()
        layout.addRow("Название:", self.doc_name)
        self.doc_path = QLineEdit()
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_file)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.doc_path)
        path_layout.addWidget(browse_btn)
        layout.addRow("Путь:", path_layout)
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_document)
        layout.addRow(self.add_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if file_path:
            self.doc_path.setText(file_path)
    def add_document(self):
        booking_id = self.booking_combo.currentData()
        doc_name = self.doc_name.text().strip()
        doc_path = self.doc_path.text().strip()
        if not (doc_name and doc_path):
            self.message_label.setText("Название и путь обязательны")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            query = """
                INSERT INTO Documents (booking_id, doc_name, doc_path, doc_create_date)
                VALUES (%s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (booking_id, doc_name, doc_path, now))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Документ добавлен")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

class EditDocumentDialog(QDialog):
    def __init__(self, document_id, parent=None):
        super().__init__(parent)
        self.document_id = document_id
        self.setWindowTitle("Редактировать документ")
        self.resize(400, 300)
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QFormLayout()
        self.booking_combo = QComboBox()
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("SELECT booking_id FROM Bookings")
            for row in cursor.fetchall():
                self.booking_combo.addItem(str(row[0]), row[0])
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
        layout.addRow("Бронирование:", self.booking_combo)
        self.doc_name = QLineEdit()
        layout.addRow("Название:", self.doc_name)
        self.doc_path = QLineEdit()
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_file)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.doc_path)
        path_layout.addWidget(browse_btn)
        layout.addRow("Путь:", path_layout)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_document)
        layout.addRow(self.save_btn)
        self.message_label = QLabel("")
        layout.addRow(self.message_label)
        self.setLayout(layout)
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if file_path:
            self.doc_path.setText(file_path)
    def load_data(self):
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT booking_id, doc_name, doc_path FROM Documents WHERE document_id = %s
            """, (self.document_id,))
            data = cursor.fetchone()
            if data:
                booking_id, doc_name, doc_path = data
                index = self.booking_combo.findData(booking_id)
                if index >= 0:
                    self.booking_combo.setCurrentIndex(index)
                self.doc_name.setText(doc_name)
                self.doc_path.setText(doc_path)
            cursor.close()
            connection.close()
        except Exception as e:
            self.message_label.setText(f"Ошибка: {e}")
    def save_document(self):
        booking_id = self.booking_combo.currentData()
        doc_name = self.doc_name.text().strip()
        doc_path = self.doc_path.text().strip()
        if not (doc_name and doc_path):
            self.message_label.setText("Название и путь обязательны")
            return
        try:
            connection = db_connect()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE Documents SET booking_id = %s, doc_name = %s, doc_path = %s
                WHERE document_id = %s
            """, (booking_id, doc_name, doc_path, self.document_id))
            connection.commit()
            cursor.close()
            connection.close()
            self.message_label.setStyleSheet("color: green;")
            self.message_label.setText("Документ обновлён")
            QTimer.singleShot(1500, self.accept)
        except Exception as e:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(f"Ошибка: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec())
#Stable last local versiom :)
