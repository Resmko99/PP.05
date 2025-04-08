import sys
import re
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel, QPushButton,
    QMessageBox, QHBoxLayout, QTableWidget, QTableWidgetItem, QInputDialog
)
from PySide6.QtCore import QTimer

API_BASE_URL = "http://your_server_ip:8000"  # Замените на адрес вашего сервера

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Отель хазбра – Авторизация")
        self.resize(400, 200)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин")
        layout.addWidget(self.login_input)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.authenticate)
        layout.addWidget(self.login_button)
        self.error_label = QLabel("")
        layout.addWidget(self.error_label)
        self.setLayout(layout)

    def authenticate(self):
        login = self.login_input.text().strip()
        password = self.password_input.text().strip()
        if not login or not password:
            self.error_label.setText("Заполните все поля")
            return
        try:
            resp = requests.post(f"{API_BASE_URL}/login", json={"user_login": login, "user_password": password})
            if resp.status_code != 200:
                self.error_label.setText(resp.json().get("detail", "Ошибка авторизации"))
                return
            user = resp.json()
            self.error_label.setText("Авторизация успешна")
            QTimer.singleShot(500, lambda: self.open_main_window(user))
        except Exception as e:
            self.error_label.setText(f"Ошибка подключения: {e}")

    def open_main_window(self, user):
        self.main_window = MainWindow(user)
        self.main_window.show()
        self.close()

class MainWindow(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle("Рабочий стол HOTEL CompanyName")
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.info_label = QLabel(f"Добро пожаловать, {self.user['first_name']} {self.user['last_name']} ({self.user['email']})")
        layout.addWidget(self.info_label)

        # Пример панели для работы с клиентами
        self.clients_table = QTableWidget()
        layout.addWidget(self.clients_table)
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить клиентов")
        self.refresh_btn.clicked.connect(self.load_clients)
        btn_layout.addWidget(self.refresh_btn)
        self.add_client_btn = QPushButton("Добавить клиента")
        self.add_client_btn.clicked.connect(self.add_client)
        btn_layout.addWidget(self.add_client_btn)
        self.del_client_btn = QPushButton("Удалить клиента")
        self.del_client_btn.clicked.connect(self.delete_client)
        btn_layout.addWidget(self.del_client_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.load_clients()

    def load_clients(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/clients")
            if resp.status_code != 200:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить клиентов")
                return
            clients = resp.json()
            self.clients_table.setRowCount(len(clients))
            self.clients_table.setColumnCount(6)
            self.clients_table.setHorizontalHeaderLabels(["ID", "Имя", "Фамилия", "Телефон", "Email", "Дата регистрации"])
            for i, client in enumerate(clients):
                self.clients_table.setItem(i, 0, QTableWidgetItem(str(client["client_id"])))
                self.clients_table.setItem(i, 1, QTableWidgetItem(client["first_name"]))
                self.clients_table.setItem(i, 2, QTableWidgetItem(client["last_name"]))
                self.clients_table.setItem(i, 3, QTableWidgetItem(client["phone"]))
                self.clients_table.setItem(i, 4, QTableWidgetItem(client["email"]))
                self.clients_table.setItem(i, 5, QTableWidgetItem(client["registered_at"]))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке клиентов: {e}")

    def add_client(self):
        first_name, ok = QInputDialog.getText(self, "Добавить клиента", "Имя:")
        if not ok or not first_name:
            return
        last_name, ok = QInputDialog.getText(self, "Добавить клиента", "Фамилия:")
        if not ok or not last_name:
            return
        phone, ok = QInputDialog.getText(self, "Добавить клиента", "Телефон:")
        if not ok or not phone:
            return
        email, ok = QInputDialog.getText(self, "Добавить клиента", "Email:")
        if not ok or not email:
            return
        if not (first_name and last_name and phone and email):
            QMessageBox.warning(self, "Внимание", "Все поля обязательны")
            return
        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё]+", first_name):
            QMessageBox.warning(self, "Внимание", "Имя должно содержать только буквы")
            return
        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё]+", last_name):
            QMessageBox.warning(self, "Внимание", "Фамилия должна содержать только буквы")
            return
        try:
            resp = requests.post(f"{API_BASE_URL}/clients", json={
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "email": email
            })
            if resp.status_code != 200:
                QMessageBox.critical(self, "Ошибка", resp.json().get("detail", "Ошибка при добавлении клиента"))
            else:
                QMessageBox.information(self, "Успех", "Клиент добавлен")
                self.load_clients()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {e}")

    def delete_client(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите клиента для удаления")
            return
        client_id = self.clients_table.item(row, 0).text()
        try:
            resp = requests.delete(f"{API_BASE_URL}/clients/{client_id}")
            if resp.status_code != 200:
                QMessageBox.critical(self, "Ошибка", resp.json().get("detail", "Ошибка при удалении клиента"))
            else:
                QMessageBox.information(self, "Успех", "Клиент удален")
                self.load_clients()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
