import sys
import psycopg2
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QMessageBox, QInputDialog, QComboBox, QFormLayout,
    QStackedWidget, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QTableWidget, QStackedWidget, QTableWidgetItem


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

# ================== Главный экран с динамическим контентом ==================
class MainWindow(QWidget):
    def __init__(self, user_id, position_id):
        super().__init__()
        self.user_id = user_id
        self.position_id = position_id
        self.setWindowTitle("Рабочий стол HOTEL CompanyName")
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
        # Основной макет с двумя областями: меню и контент
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Меню (постоянное)
        self.menu_layout = QVBoxLayout()
        self.menu_layout.setSpacing(10)
        # Кнопки меню – для демонстрации возьмем несколько пунктов
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

        # Область контента – будет меняться в зависимости от выбранного пункта меню
        self.content_stack = QStackedWidget()
        # Добавляем страницы – здесь приведены примерные заготовки:
        self.page_admin = self.create_admin_page()
        self.page_clients = ClientsPanel()       # ранее реализованная панель для клиентов
        self.page_rooms = RoomsPanel()           # для номеров
        self.page_bookings = BookingsPanel()     # для бронирований
        self.page_payments = PaymentsPanel()     # для платежей
        self.page_services = ServicesPanel()     # для доп. услуг
        self.page_documents = DocumentsPanel()   # для документов
        self.content_stack.addWidget(self.page_admin)      # индекс 0
        self.content_stack.addWidget(self.page_clients)      # индекс 1
        self.content_stack.addWidget(self.page_rooms)        # индекс 2
        self.content_stack.addWidget(self.page_bookings)     # индекс 3
        self.content_stack.addWidget(self.page_payments)     # индекс 4
        self.content_stack.addWidget(self.page_services)     # индекс 5
        self.content_stack.addWidget(self.page_documents)    # индекс 6

        main_layout.addLayout(self.menu_layout, 1)
        main_layout.addWidget(self.content_stack, 4)

        # Верхняя панель с информацией о пользователе
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

    def create_admin_page(self):
        """Создает страницу для админ-функционала с кнопками для управления пользователями."""
        page = QWidget()
        layout = QVBoxLayout()
        info_label = QLabel("Админ: здесь можно редактировать пользователей")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        add_user_btn = QPushButton("Добавить пользователя")
        add_user_btn.clicked.connect(lambda: self.open_add_user_window())
        btn_layout.addWidget(add_user_btn)
        unblock_btn = QPushButton("Снять блокировку")
        unblock_btn.clicked.connect(lambda: self.unblock_user())
        btn_layout.addWidget(unblock_btn)
        block_btn = QPushButton("Заблокировать")
        block_btn.clicked.connect(lambda: self.block_user())
        btn_layout.addWidget(block_btn)
        layout.addLayout(btn_layout)
        page.setLayout(layout)
        return page

    def open_add_user_window(self):
        self.add_user_window = AdminAddUserWindow()
        # Вместо всплывающего окна можно заменить содержимое контент-области
        # Например, добавим add_user_window как новую страницу в stack
        self.content_stack.addWidget(self.add_user_window)
        self.content_stack.setCurrentWidget(self.add_user_window)

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
                self.load_user_info()
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
                self.load_user_info()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка блокировки: {e}")

# ================== Примеры панелей для остальных таблиц ==================
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
        QMessageBox.information(self, "Добавить", "Функция добавления клиента не реализована")
    def edit_client(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования клиента не реализована")
    def delete_client(self):
        QMessageBox.information(self, "Удалить", "Функция удаления клиента не реализована")

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
            cursor.execute("SELECT room_id, room_number, floor, capacity, category_id, current_status, departure_date FROM Rooms ORDER BY room_id")
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(7)
            self.table.setHorizontalHeaderLabels(["ID", "Номер", "Этаж", "Вместимость", "Категория", "Статус", "Дата выезда"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки номеров: {e}")
    def add_room(self):
        QMessageBox.information(self, "Добавить", "Функция добавления номера не реализована")
    def edit_room(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования номера не реализована")
    def delete_room(self):
        QMessageBox.information(self, "Удалить", "Функция удаления номера не реализована")

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
            cursor.execute("SELECT booking_id, client_id, user_id, booking_date, arrival_date, departure_date, booking_status_id, total_cost FROM Bookings ORDER BY booking_id")
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels(["ID", "Клиент", "Пользователь", "Дата бронирования", "Прибытие", "Выезд", "Статус", "Стоимость"])
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            cursor.close()
            connection.close()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки бронирований: {e}")
    def add_booking(self):
        QMessageBox.information(self, "Добавить", "Функция добавления бронирования не реализована")
    def edit_booking(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования бронирования не реализована")
    def delete_booking(self):
        QMessageBox.information(self, "Удалить", "Функция удаления бронирования не реализована")

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
            cursor.execute("SELECT payment_id, booking_id, payment_date, amount, payment_method_id FROM Payments ORDER BY payment_id")
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
        QMessageBox.information(self, "Добавить", "Функция добавления платежа не реализована")
    def edit_payment(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования платежа не реализована")
    def delete_payment(self):
        QMessageBox.information(self, "Удалить", "Функция удаления платежа не реализована")

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
            cursor.execute("SELECT service_id, service_name, price, description FROM AdditionalServices ORDER BY service_id")
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
        QMessageBox.information(self, "Добавить", "Функция добавления услуги не реализована")
    def edit_service(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования услуги не реализована")
    def delete_service(self):
        QMessageBox.information(self, "Удалить", "Функция удаления услуги не реализована")

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
            cursor.execute("SELECT document_id, booking_id, doc_name, doc_path, doc_create_date FROM Documents ORDER BY document_id")
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
        QMessageBox.information(self, "Добавить", "Функция добавления документа не реализована")
    def edit_document(self):
        QMessageBox.information(self, "Редактировать", "Функция редактирования документа не реализована")
    def delete_document(self):
        QMessageBox.information(self, "Удалить", "Функция удаления документа не реализована")

# ================== Окно управления данными ==================
class DataManagementWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Управление данными")
        self.resize(1200, 800)
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
        self.menu_layout = QVBoxLayout()
        self.stack = QStackedWidget()

        # Добавляем страницы – примерные панели для таблиц:
        self.page_clients = ClientsPanel()
        self.page_rooms = RoomsPanel()
        self.page_bookings = BookingsPanel()
        self.page_payments = PaymentsPanel()
        self.page_services = ServicesPanel()
        self.page_documents = DocumentsPanel()

        self.stack.addWidget(self.page_clients)    # индекс 0
        self.stack.addWidget(self.page_rooms)        # индекс 1
        self.stack.addWidget(self.page_bookings)     # индекс 2
        self.stack.addWidget(self.page_payments)     # индекс 3
        self.stack.addWidget(self.page_services)     # индекс 4
        self.stack.addWidget(self.page_documents)    # индекс 5

        btn_clients = QPushButton("Клиенты")
        btn_clients.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.menu_layout.addWidget(btn_clients)

        btn_rooms = QPushButton("Номера")
        btn_rooms.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.menu_layout.addWidget(btn_rooms)

        btn_bookings = QPushButton("Бронирования")
        btn_bookings.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.menu_layout.addWidget(btn_bookings)

        btn_payments = QPushButton("Платежи")
        btn_payments.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.menu_layout.addWidget(btn_payments)

        btn_services = QPushButton("Доп. услуги")
        btn_services.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.menu_layout.addWidget(btn_services)

        btn_documents = QPushButton("Документы")
        btn_documents.clicked.connect(lambda: self.stack.setCurrentIndex(5))
        self.menu_layout.addWidget(btn_documents)

        self.menu_layout.addStretch()
        main_layout.addLayout(self.menu_layout)
        main_layout.addWidget(self.stack)
        self.setLayout(main_layout)

# ================== Окно добавления пользователя ==================
class AdminAddUserWindow(QWidget):
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
        # Пароль не запрашивается – всегда DEFAULT_PASSWORD
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
