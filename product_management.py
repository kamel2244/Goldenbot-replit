import sys
import os
import sqlite3
import shutil
import csv
import uuid
import barcode
from barcode.writer import ImageWriter
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLineEdit, QPushButton, QLabel, QHeaderView,
    QMessageBox, QFileDialog, QDialog, QFormLayout, QDateEdit,
    QGroupBox, QComboBox, QCheckBox, QScrollArea, QSpinBox
)
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QTextDocument, QPixmap, QImage, QPainter, QFont
from PyQt5.QtCore import Qt, QSize, QDate, QRectF, QSizeF
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from escpos.printer import Usb

DB_FILE = "golden_tech.db"
IMAGE_FOLDER = "product_images"
BARCODE_FOLDER = "barcodes"

class ProductManagementInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("إدارة المنتجات")
        self.resize(1200, 750)
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                padding: 8px 12px;
                border-radius: 4px;
                min-width: 100px;
            }
            QTableWidget {
                border: 1px solid #e0e0e0;
                gridline-color: #f0f0f0;
            }
            QHeaderView::section {
                background-color: #f8f8f8;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                font-weight: bold;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #4d90fe;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        if not os.path.exists(IMAGE_FOLDER):
            os.makedirs(IMAGE_FOLDER)
        if not os.path.exists(BARCODE_FOLDER):
            os.makedirs(BARCODE_FOLDER)

        self.conn = None
        self.cursor = None
        self.create_tables()
        self.init_ui()
        self.load_products()
        self.image_path = ""

    def check_db_connection(self):
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(DB_FILE)
                self.cursor = self.conn.cursor()
            elif hasattr(self.conn, '_isclosed') and self.conn._isclosed:
                self.conn = sqlite3.connect(DB_FILE)
                self.cursor = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في الاتصال", f"فشل في الاتصال بقاعدة البيانات: {str(e)}")
            return False

    def create_tables(self):
        if not self.check_db_connection():
            return False
        
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    purchase_price REAL NOT NULL DEFAULT 0 CHECK(purchase_price >= 0),
                    sale_price REAL NOT NULL DEFAULT 0 CHECK(sale_price >= 0),
                    expiry_date TEXT,
                    barcode TEXT UNIQUE,
                    image_path TEXT,
                    supplier_name TEXT,
                    supplier_phone TEXT
                )
            """)
            
            self.cursor.execute("PRAGMA table_info(products)")
            existing_columns = [column[1] for column in self.cursor.fetchall()]
            
            required_columns = [
                ("name", "TEXT NOT NULL"),
                ("quantity", "INTEGER DEFAULT 0"),
                ("purchase_price", "REAL NOT NULL DEFAULT 0 CHECK(purchase_price >= 0)"),
                ("sale_price", "REAL NOT NULL DEFAULT 0 CHECK(sale_price >= 0)"),
                ("expiry_date", "TEXT"),
                ("barcode", "TEXT UNIQUE"),
                ("image_path", "TEXT"),
                ("supplier_name", "TEXT"),
                ("supplier_phone", "TEXT")
            ]
            
            for column, definition in required_columns:
                if column not in existing_columns:
                    try:
                        self.cursor.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
                    except sqlite3.Error as e:
                        print(f"فشل في إضافة العمود {column}: {str(e)}")
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في إنشاء/تعديل الجداول: {str(e)}")
            return False

    def init_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Left panel (buttons)
        left_panel = QGroupBox("القائمة")
        left_panel.setFixedWidth(220)
        left = QVBoxLayout(left_panel)
        left.setSpacing(15)
        left.setContentsMargins(10, 20, 10, 10)
        
        buttons = [
            ("➕ إضافة منتج", "#4CAF50", self.add_product),
            ("✏️ تعديل منتج", "#FFC107", self.edit_product),
            ("🗑️ حذف منتج", "#F44336", self.delete_product),
            ("🖨️ طباعة القائمة", "#2196F3", self.print_products_list),
            ("🏷️ طباعة باركود", "#9C27B0", self.print_barcode),
            ("💰 طباعة السعر", "#FF9800", self.print_price),
            ("⬇️ استيراد CSV", "#607D8B", self.import_from_csv),
            ("⬆️ تصدير CSV", "#795548", self.export_to_csv),
        ]
        
        for text, color, handler in buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(45)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    border: none;
                    text-align: right;
                    padding-right: 15px;
                }}
                QPushButton:hover {{
                    background-color: {self.darken_color(color)};
                }}
            """)
            btn.setIconSize(QSize(24, 24))
            btn.clicked.connect(handler)
            left.addWidget(btn)
        
        left.addStretch()
        main_layout.addWidget(left_panel)
        
        # Right panel (main content)
        right_panel = QWidget()
        right = QVBoxLayout(right_panel)
        right.setSpacing(20)
        
        title = QLabel("إدارة المنتجات")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
        """)
        right.addWidget(title)
        
        # Search box
        search_container = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 بحث بالاسم أو الباركود")
        self.search_box.textChanged.connect(self.search_products)
        self.search_box.setFixedHeight(40)
        self.search_box.setStyleSheet("""
            QLineEdit {{
                padding-left: 35px;
                border-radius: 4px;
                border: 1px solid #ddd;
                font-size: 15px;
            }}
        """)
        search_container.addWidget(self.search_box)
        right.addLayout(search_container)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "📦 الاسم", "📊 الكمية", "💰 سعر الشراء",
            "💸 سعر البيع", "📅 تاريخ الانتهاء", "🏷 الباركود", "🖼 الصورة"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {{
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
        """)
        
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(5, 150)
        
        right.addWidget(self.table)
        main_layout.addWidget(right_panel)

    def darken_color(self, hex_color, factor=0.8):
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, int(c * factor)) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

    def load_products(self):
        if not self.check_db_connection():
            return False
        try:
            self.cursor.execute(
                "SELECT name, quantity, purchase_price, sale_price, expiry_date, barcode, image_path FROM products"
            )
            rows = self.cursor.fetchall()
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    
                    if j == 1:  # الكمية
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                        item.setText(f"{val:,}")
                    elif j in (2, 3):  # الأسعار
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        item.setText(f"{float(val):,.2f}" if val else "0.00")
                    elif j == 5:  # الباركود
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    elif j == 6:  # الصورة
                        if val and os.path.exists(val):
                            item.setText("🖼️ متوفرة")
                        else:
                            item.setText("❌ غير متوفرة")
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    
                    self.table.setItem(i, j, item)
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في تحميل المنتجات: {str(e)}")
            return False

    def search_products(self):
        term = self.search_box.text().strip()
        if not term:
            self.load_products()
            return
            
        if not self.check_db_connection():
            return
            
        try:
            like = f"%{term}%"
            self.cursor.execute(
                "SELECT name, quantity, purchase_price, sale_price, expiry_date, barcode, image_path "
                "FROM products WHERE name LIKE ? OR barcode LIKE ?", (like, like))
            rows = self.cursor.fetchall()
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    
                    if j == 1:
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                        item.setText(f"{val:,}")
                    elif j in (2, 3):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        item.setText(f"{float(val):,.2f}" if val else "0.00")
                    elif j == 5:
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    elif j == 6:
                        if val and os.path.exists(val):
                            item.setText("🖼️ متوفرة")
                        else:
                            item.setText("❌ غير متوفرة")
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    
                    self.table.setItem(i, j, item)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في البحث: {str(e)}")

    def add_product(self):
        self.product_dialog("➕ إضافة منتج")

    def edit_product(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "⚠️", "يرجى تحديد منتج.")
            return
            
        if not self.check_db_connection():
            return
            
        try:
            bc = self.table.item(r, 5).text()
            self.cursor.execute(
                "SELECT name, quantity, purchase_price, sale_price, expiry_date, barcode, image_path, supplier_name, supplier_phone "
                "FROM products WHERE barcode=?", (bc,))
            rec = self.cursor.fetchone()
            
            if rec:
                self.product_dialog("✏️ تعديل منتج", rec)
            else:
                QMessageBox.warning(self, "⚠️", "المنتج المحدد غير موجود في قاعدة البيانات.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في تحميل بيانات المنتج: {str(e)}")

    def product_dialog(self, title, record=None):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedWidth(600)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        # Product info group
        product_group = QGroupBox("معلومات المنتج")
        product_layout = QFormLayout(product_group)
        
        name = QLineEdit(record[0] if record else "")
        name.setPlaceholderText("اسم المنتج")
        
        qty = QLineEdit(str(record[1]) if record else "0")
        qty.setValidator(QIntValidator(0, 999999))
        qty.setPlaceholderText("الكمية")
        
        purchase = QLineEdit(str(record[2]) if record else "")
        purchase.setValidator(QDoubleValidator(0.01, 9999999, 2))
        purchase.setPlaceholderText("سعر الشراء")
        
        sale = QLineEdit(str(record[3]) if record else "")
        sale.setValidator(QDoubleValidator(0.01, 9999999, 2))
        sale.setPlaceholderText("سعر البيع")
        
        expiry = QDateEdit(
            QDate.fromString(record[4], "yyyy-MM-dd") if record and len(record) > 4 and record[4] else QDate.currentDate()
        )
        expiry.setCalendarPopup(True)
        expiry.setDisplayFormat("yyyy/MM/dd")
        
        barcode_edit = QLineEdit(record[5] if record else "")
        barcode_edit.setPlaceholderText("الباركود (يُولد تلقائيًا إذا تُرك فارغًا)")
        
        product_layout.addRow("اسم المنتج:", name)
        product_layout.addRow("الكمية:", qty)
        product_layout.addRow("سعر الشراء:", purchase)
        product_layout.addRow("سعر البيع:", sale)
        product_layout.addRow("تاريخ الانتهاء:", expiry)
        product_layout.addRow("الباركود:", barcode_edit)
        
        # Supplier info group
        supplier_group = QGroupBox("معلومات المورد")
        supplier_layout = QFormLayout(supplier_group)
        
        supplier_name = QLineEdit(record[7] if record and len(record) > 7 else "")
        supplier_name.setPlaceholderText("اسم المورد")
        
        supplier_phone = QLineEdit(record[8] if record and len(record) > 8 else "")
        supplier_phone.setPlaceholderText("هاتف المورد")
        supplier_phone.setValidator(QIntValidator(0, 999999999))
        
        supplier_layout.addRow("اسم المورد:", supplier_name)
        supplier_layout.addRow("هاتف المورد:", supplier_phone)
        
        # Image upload
        image_group = QGroupBox("صورة المنتج")
        image_layout = QVBoxLayout(image_group)
        
        self.image_path = record[6] if record and record[6] else ""
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(150)
        self.image_label.setStyleSheet("background-color: #f8f8f8; border: 1px dashed #ddd;")
        
        if self.image_path and os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path).scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("اضغط لاختيار صورة")
        
        upload_btn = QPushButton("اختيار صورة")
        upload_btn.setStyleSheet("background-color: #e0e0e0;")
        upload_btn.clicked.connect(lambda: self.upload_image(dlg))
        
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(upload_btn)
        
        form.addRow(product_group)
        form.addRow(supplier_group)
        form.addRow(image_group)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.setFixedHeight(45)
        save_btn.setStyleSheet("""
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            font-size: 15px;
        """)
        save_btn.clicked.connect(lambda: self.save_product(
            dlg, name, qty, purchase, sale, expiry,
            barcode_edit, supplier_name, supplier_phone, record
        ))
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFixedHeight(45)
        cancel_btn.setStyleSheet("""
            background-color: #f44336;
            color: white;
            font-weight: bold;
            font-size: 15px;
        """)
        cancel_btn.clicked.connect(dlg.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        dlg.exec_()

    def upload_image(self, parent):
        file_path, _ = QFileDialog.getOpenFileName(parent, "اختر صورة المنتج", "",
                                                 "الصور (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return
            
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "خطأ", "الصورة المحددة غير موجودة.")
            return
            
        ext = os.path.splitext(file_path)[1]
        new_filename = f"{uuid.uuid4().hex}{ext}"
        new_path = os.path.join(IMAGE_FOLDER, new_filename)
        
        try:
            shutil.copy(file_path, new_path)
            self.image_path = new_path
            pixmap = QPixmap(new_path).scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل تحميل الصورة: {str(e)}")

    def save_product(self, dlg, name, qty, purchase, sale, expiry,
                    barcode_edit, supplier_name, supplier_phone, record=None):
        if not self.check_db_connection():
            return
            
        n, q, p, s = name.text().strip(), qty.text().strip(), purchase.text().strip(), sale.text().strip()
        exp = expiry.date().toString("yyyy-MM-dd")
        bc = barcode_edit.text().strip()
        sup_name = supplier_name.text().strip()
        sup_phone = supplier_phone.text().strip()
        
        if not all([n, q, p, s]):
            QMessageBox.warning(self, "⚠️", "يرجى ملء جميع الحقول الأساسية.")
            return
            
        try:
            q_val = int(q.replace(",", ""))
            p_val = float(p.replace(",", ""))
            s_val = float(s.replace(",", ""))
            
            if q_val < 0:
                QMessageBox.warning(self, "⚠️", "الكمية لا يمكن أن تكون سالبة.")
                return
                
            if p_val <= 0:
                QMessageBox.warning(self, "⚠️", "سعر الشراء يجب أن يكون أكبر من صفر.")
                return
                
            if s_val <= 0:
                QMessageBox.warning(self, "⚠️", "سعر البيع يجب أن يكون أكبر من صفر.")
                return
                
            if s_val < p_val:
                QMessageBox.warning(self, "⚠️", "سعر البيع يجب أن يكون أكبر من أو يساوي سعر الشراء.")
                return
                
            if expiry.date() < QDate.currentDate():
                QMessageBox.warning(self, "⚠️", "تاريخ الانتهاء لا يمكن أن يكون في الماضي.")
                return
                
        except ValueError:
            QMessageBox.warning(self, "⚠️", "خطأ في إدخال القيم الرقمية.")
            return
            
        if not bc:
            try:
                last_id = self.cursor.execute("SELECT MAX(id) FROM products").fetchone()[0] or 0
                bc = f"CB{str(last_id + 1).zfill(8)}"
            except sqlite3.Error as e:
                QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في إنشاء باركود جديد: {str(e)}")
                return
                
        try:
            if record:
                self.cursor.execute(
                    "UPDATE products SET name=?, quantity=?, purchase_price=?, sale_price=?,"
                    " expiry_date=?, barcode=?, image_path=?, supplier_name=?, supplier_phone=?"
                    " WHERE barcode=?", (n, q_val, p_val, s_val, exp, bc, self.image_path, sup_name, sup_phone, record[5])
                )
            else:
                self.cursor.execute(
                    "INSERT INTO products (name, quantity, purchase_price, sale_price,"
                    " expiry_date, barcode, image_path, supplier_name, supplier_phone)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (n, q_val, p_val, s_val, exp, bc, self.image_path, sup_name, sup_phone)
                )
            
            self.conn.commit()
            self.load_products()
            dlg.accept()
            QMessageBox.information(self, "✅", "تم الحفظ بنجاح.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "❌", "⚠️ الباركود مستخدم مسبقًا. غيّر الباركود أو اتركه فارغًا.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في حفظ المنتج: {str(e)}")

    def delete_product(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "⚠️", "يرجى تحديد منتج.")
            return
            
        if not self.check_db_connection():
            return
            
        bc = self.table.item(row, 5).text()
        name = self.table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المنتج '{name}'؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # حذف الصورة المرتبطة بالمنتج إذا كانت موجودة
                image_path = self.cursor.execute("SELECT image_path FROM products WHERE barcode=?", (bc,)).fetchone()[0]
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        print(f"Failed to delete image: {str(e)}")
                
                # حذف المنتج من قاعدة البيانات
                self.cursor.execute("DELETE FROM products WHERE barcode=?", (bc,))
                self.conn.commit()
                self.load_products()
                QMessageBox.information(self, "✅", "تم حذف المنتج بنجاح.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في حذف المنتج: {str(e)}")

    def print_products_list(self):
        if not self.check_db_connection():
            return
            
        # إنشاء نافذة اختيار المنتجات
        dlg = QDialog(self)
        dlg.setWindowTitle("اختر المنتجات للطباعة")
        dlg.setFixedSize(600, 500)
        layout = QVBoxLayout(dlg)
        
        # إضافة عنصر التمرير
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # جلب جميع المنتجات
        try:
            self.cursor.execute("SELECT id, name FROM products")
            products = self.cursor.fetchall()
            
            self.checkboxes = []
            for product in products:
                chk = QCheckBox(f"{product[0]} - {product[1]}")
                chk.setChecked(True)
                self.checkboxes.append((product[0], chk))
                scroll_layout.addWidget(chk)
            
            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)
            
            # إضافة خيارات الطباعة
            print_options = QGroupBox("خيارات الطباعة")
            print_layout = QFormLayout(print_options)
            
            self.per_page = QLineEdit("20")
            self.per_page.setValidator(QIntValidator(1, 100))
            print_layout.addRow("عدد المنتجات في الصفحة:", self.per_page)
            
            # إضافة خانة البحث
            self.search_print = QLineEdit()
            self.search_print.setPlaceholderText("🔍 بحث عن المنتجات")
            self.search_print.textChanged.connect(self.filter_print_products)
            print_layout.addRow("بحث:", self.search_print)
            
            layout.addWidget(print_options)
            
            # أزرار التنفيذ
            btn_layout = QHBoxLayout()
            print_btn = QPushButton("طباعة")
            print_btn.clicked.connect(lambda: self.print_selected_products(dlg))
            cancel_btn = QPushButton("إلغاء")
            cancel_btn.clicked.connect(dlg.reject)
            
            btn_layout.addWidget(print_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)
            
            dlg.exec_()
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في تحميل المنتجات: {str(e)}")

    def filter_print_products(self):
        search_term = self.search_print.text().lower()
        for product_id, checkbox in self.checkboxes:
            product_text = checkbox.text().lower()
            checkbox.setVisible(search_term in product_text)

    def print_selected_products(self, dlg):
        try:
            per_page = int(self.per_page.text())
            selected_ids = [cb[0] for cb in self.checkboxes if cb[1].isChecked()]
            
            if not selected_ids:
                QMessageBox.warning(self, "تحذير", "لم يتم اختيار أي منتجات للطباعة")
                return
                
            # جلب بيانات المنتجات المختارة
            placeholders = ','.join(['?'] * len(selected_ids))
            query = f"SELECT name, quantity, purchase_price, sale_price, expiry_date, barcode, supplier_name FROM products WHERE id IN ({placeholders})"
            self.cursor.execute(query, selected_ids)
            products = self.cursor.fetchall()
            
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setOrientation(QPrinter.Portrait)  # تغيير إلى وضع Portrait بدلاً من Landscape
            printer.setFullPage(False)
            
            if QPrintDialog(printer, self).exec_() == QPrintDialog.Accepted:
                doc = QTextDocument()
                html = """
                <style>
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        font-family: Arial, sans-serif;
                        font-size: 16pt;
                        margin-bottom: 20px;
                    }
                    th {
                        background-color: #f2f2f2;
                        padding: 12px;
                        text-align: center;
                        border: 1px solid #ddd;
                        font-weight: bold;
                        font-size: 18pt;
                    }
                    td {
                        padding: 12px;
                        text-align: center;
                        border: 1px solid #ddd;
                    }
                    h2 {
                        text-align: center;
                        margin-bottom: 15px;
                        font-size: 24pt;
                    }
                    .date {
                        text-align: center;
                        color: #666;
                        margin-bottom: 20px;
                        font-size: 14pt;
                    }
                </style>
                """
                
                # تقسيم المنتجات إلى صفحات
                for i in range(0, len(products), per_page):
                    page_products = products[i:i+per_page]
                    
                    html += (
                        "<h2>قائمة المنتجات</h2>"
                        "<p class='date'>تاريخ الطباعة: " + datetime.now().strftime("%Y/%m/%d %H:%M") + "</p>"
                        "<table>"
                        "<tr>"
                        "<th width='25%'>الاسم</th><th width='10%'>الكمية</th><th width='12%'>سعر الشراء</th>"
                        "<th width='12%'>سعر البيع</th><th width='12%'>تاريخ الانتهاء</th><th width='15%'>الباركود</th>"
                        "<th width='14%'>المورد</th></tr>"
                    )
                    
                    for row in page_products:
                        html += (
                            f"<tr><td>{row[0]}</td><td>{row[1]:,}</td><td>{row[2]:,.2f}</td>"
                            f"<td>{row[3]:,.2f}</td><td>{row[4] if row[4] else '-'}</td><td>{row[5]}</td>"
                            f"<td>{row[6] if row[6] else '-'}</td></tr>"
                        )
                    
                    html += "</table>"
                    
                    # إضافة فاصل بين الصفحات
                    if i + per_page < len(products):
                        html += "<div style='page-break-after:always;'></div>"
                
                doc.setHtml(html)
                doc.setPageSize(QSizeF(printer.pageRect().size()))
                
                # ضبط الهوامش وحجم المحتوى
                margin = 20  # هامش 20 بكسل من جميع الجهات
                doc.setPageSize(QSizeF(printer.pageRect().width() - margin * 2, 
                               printer.pageRect().height() - margin * 2))
                
                painter = QPainter(printer)
                painter.translate(margin, margin)
                doc.drawContents(painter)
                painter.end()
                
                dlg.accept()
                
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء الطباعة: {str(e)}")

    def print_barcode(self):
        # إنشاء نافذة اختيار المنتجات للطباعة
        dlg = QDialog(self)
        dlg.setWindowTitle("طباعة الباركود")
        dlg.setFixedSize(800, 600)
        layout = QVBoxLayout(dlg)
        
        # إنشاء جدول لاختيار المنتجات
        self.print_table = QTableWidget()
        self.print_table.setColumnCount(4)
        self.print_table.setHorizontalHeaderLabels(["اختيار", "اسم المنتج", "الباركود", "عدد النسخ"])
        
        # إضافة خانة "اختيار الكل" في رأس العمود الأول
        header = self.print_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.print_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # جلب جميع المنتجات من قاعدة البيانات
        try:
            self.cursor.execute("SELECT name, barcode FROM products")
            products = self.cursor.fetchall()
            self.print_table.setRowCount(len(products))
            
            # إضافة خانة "اختيار الكل" في رأس العمود الأول
            select_all_header = QCheckBox()
            select_all_header.stateChanged.connect(self.toggle_all_products)
            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.addWidget(select_all_header)
            header_layout.setAlignment(Qt.AlignCenter)
            header_layout.setContentsMargins(0, 0, 0, 0)
            self.print_table.setCellWidget(0, 0, header_widget)
            
            for row, (name, barcode_value) in enumerate(products):
                # إضافة خانة اختيار
                chk = QCheckBox()
                chk.setChecked(True)
                chk_widget = QWidget()
                chk_layout = QHBoxLayout(chk_widget)
                chk_layout.addWidget(chk)
                chk_layout.setAlignment(Qt.AlignCenter)
                chk_layout.setContentsMargins(0, 0, 0, 0)
                self.print_table.setCellWidget(row, 0, chk_widget)
                
                # إضافة اسم المنتج
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
                self.print_table.setItem(row, 1, name_item)
                
                # إضافة الباركود
                barcode_item = QTableWidgetItem(barcode_value)
                barcode_item.setFlags(barcode_item.flags() ^ Qt.ItemIsEditable)
                self.print_table.setItem(row, 2, barcode_item)
                
                # إضافة عدد النسخ
                spin = QSpinBox()
                spin.setMinimum(1)
                spin.setMaximum(100)
                spin.setValue(1)
                spin_widget = QWidget()
                spin_layout = QHBoxLayout(spin_widget)
                spin_layout.addWidget(spin)
                spin_layout.setAlignment(Qt.AlignCenter)
                spin_layout.setContentsMargins(0, 0, 0, 0)
                self.print_table.setCellWidget(row, 3, spin_widget)
        
        except sqlite3.Error as e:
            QMessageBox.critical(self, "خطأ في قاعدة البيانات", f"فشل في تحميل المنتجات: {str(e)}")
            dlg.reject()
            return
        
        # إضافة خيارات حجم الباركود
        barcode_size_group = QGroupBox("خيارات الطباعة")
        size_layout = QHBoxLayout(barcode_size_group)
        
        # إعدادات الطابعة الحرارية
        self.paper_size = QComboBox()
        paper_sizes = ["40x20 مم (صغير)", "50x30 مم (متوسط)", "58x40 مم (كبير)"]
        self.paper_size.addItems(paper_sizes)
        size_layout.addWidget(QLabel("حجم الورقة:"))
        size_layout.addWidget(self.paper_size)
        size_layout.addStretch()
        
        # إضافة خيار إظهار السعر
        self.show_price = QCheckBox("إظهار السعر")
        self.show_price.setChecked(True)
        size_layout.addWidget(self.show_price)
        
        # أزرار التنفيذ
        btn_layout = QHBoxLayout()
        print_btn = QPushButton("طباعة")
        print_btn.clicked.connect(lambda: self.print_selected_barcodes(dlg))
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(dlg.reject)
        
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(cancel_btn)
        
        # ترتيب العناصر في النافذة
        layout.addWidget(self.print_table)
        layout.addWidget(barcode_size_group)
        layout.addLayout(btn_layout)
        
        dlg.exec_()

    def toggle_all_products(self, state):
        """تحديد أو إلغاء تحديد جميع المنتجات"""
        for row in range(self.print_table.rowCount()):
            checkbox = self.print_table.cellWidget(row, 0).findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(state == Qt.Checked)

    def print_selected_barcodes(self, parent_dialog):
        try:
            # جلب المنتجات المحددة للطباعة
            barcodes_to_print = []
            for row in range(self.print_table.rowCount()):
                if self.print_table.cellWidget(row, 0).findChild(QCheckBox).isChecked():
                    barcode_value = self.print_table.item(row, 2).text()
                    copies = self.print_table.cellWidget(row, 3).findChild(QSpinBox).value()
                    barcodes_to_print.append((barcode_value, copies))
            
            if not barcodes_to_print:
                QMessageBox.warning(self, "تحذير", "لم يتم اختيار أي منتجات للطباعة")
                return
            
            # محاولة استخدام طابعة ESC/POS مباشرة (الطابعات الحرارية)
            try:
                # تغيير معرف الطابعة حسب الطابعة الخاصة بك
                printer = Usb(0x04b8, 0x0202)  # مثال لمعرف طابعة Epson
                
                # تحديد حجم الورقة حسب الاختيار
                paper_size = self.paper_size.currentText()
                
                for barcode_value, copies in barcodes_to_print:
                    for _ in range(copies):
                        # جلب بيانات المنتج
                        self.cursor.execute(
                            "SELECT name, sale_price FROM products WHERE barcode=?", (barcode_value,))
                        product_data = self.cursor.fetchone()
                        product_name = product_data[0] if product_data else ""
                        product_price = product_data[1] if product_data else 0
                        
                        # ضبط إعدادات الطباعة حسب حجم الورقة
                        if "صغير" in paper_size:
                            printer.set(align='center', width=1, height=1)
                            name_font_size = 1
                            price_font_size = 1
                            barcode_height = 40
                        elif "متوسط" in paper_size:
                            printer.set(align='center', width=2, height=2)
                            name_font_size = 2
                            price_font_size = 2
                            barcode_height = 60
                        else:  # كبير
                            printer.set(align='center', width=3, height=3)
                            name_font_size = 3
                            price_font_size = 3
                            barcode_height = 80
                        
                        # طباعة اسم المنتج
                        printer.set(font='a', height=name_font_size, width=name_font_size)
                        printer.text(f"{product_name}\n")
                        
                        # طباعة السعر إذا كان مفعل
                        if self.show_price.isChecked():
                            printer.set(font='b', height=price_font_size, width=price_font_size)
                            printer.text(f"Prix: {product_price:,.2f} DA\n")
                        
                        # طباعة الباركود
                        printer.barcode(
                            barcode_value, 
                            "CODE128", 
                            width=2,     # عرض متوسط (1-6)
                            height=barcode_height,   # ارتفاع مناسب (1-255)
                            align="center",
                            function_type="A"
                        )
                        printer.text("\n\n")  # إضافة مسافات بعد الباركود
                
                printer.cut()
                parent_dialog.accept()
                return
                
            except Exception as e:
                print(f"فشل الطباعة المباشرة، سيتم استخدام الطباعة العادية: {str(e)}")
            
            # إذا فشلت الطباعة المباشرة، استخدم الطابعة العادية مع مقاييس أوراق الطابعة الحرارية
            printer = QPrinter(QPrinter.HighResolution)
            printer.setFullPage(True)
            
            # تحديد حجم الصفحة بناءً على حجم الورقة الحرارية
            paper_size = self.paper_size.currentText()
            if "صغير" in paper_size:  # 40x20 مم
                printer.setPageSize(QPrinter.Custom)
                printer.setPaperSize(QSizeF(40, 20), QPrinter.Millimeter)
            elif "متوسط" in paper_size:  # 50x30 مم
                printer.setPageSize(QPrinter.Custom)
                printer.setPaperSize(QSizeF(50, 30), QPrinter.Millimeter)
            else:  # كبير 58x40 مم
                printer.setPageSize(QPrinter.Custom)
                printer.setPaperSize(QSizeF(58, 40), QPrinter.Millimeter)
            
            if QPrintDialog(printer, self).exec_() == QPrintDialog.Accepted:
                painter = QPainter()
                if not painter.begin(printer):
                    QMessageBox.warning(self, "خطأ", "فشل في بدء الطباعة")
                    return
                
                try:
                    # حساب أبعاد الصفحة بالمليمتر
                    page_width_mm = printer.width() / printer.logicalDpiX() * 25.4
                    page_height_mm = printer.height() / printer.logicalDpiY() * 25.4
                    
                    # طباعة كل باركود بالعدد المطلوب
                    for barcode_value, copies in barcodes_to_print:
                        for _ in range(copies):
                            # جلب بيانات المنتج
                            self.cursor.execute(
                                "SELECT name, sale_price FROM products WHERE barcode=?", (barcode_value,))
                            product_data = self.cursor.fetchone()
                            product_name = product_data[0] if product_data else ""
                            product_price = product_data[1] if product_data else 0
                            
                            # إنشاء صورة الباركود
                            try:
                                code_class = barcode.get_barcode_class('code128')
                            except:
                                code_class = barcode.get_barcode_class('ean13')
                            
                            # تحديد أبعاد الباركود بناءً على حجم الورقة
                            if "صغير" in paper_size:
                                options = {
                                    'module_width': 0.25,
                                    'module_height': 8,
                                    'font_size': 0,
                                    'quiet_zone': 3,
                                    'text_distance': 1,
                                    'background': 'white',
                                    'foreground': 'black',
                                    'write_text': False
                                }
                                name_font_size = 8
                                price_font_size = 10
                            elif "متوسط" in paper_size:
                                options = {
                                    'module_width': 0.3,
                                    'module_height': 12,
                                    'font_size': 0,
                                    'quiet_zone': 4,
                                    'text_distance': 1,
                                    'background': 'white',
                                    'foreground': 'black',
                                    'write_text': False
                                }
                                name_font_size = 10
                                price_font_size = 12
                            else:  # كبير
                                options = {
                                    'module_width': 0.35,
                                    'module_height': 16,
                                    'font_size': 0,
                                    'quiet_zone': 5,
                                    'text_distance': 1,
                                    'background': 'white',
                                    'foreground': 'black',
                                    'write_text': False
                                }
                                name_font_size = 12
                                price_font_size = 14
                            
                            code = code_class(barcode_value, writer=ImageWriter())
                            filename = os.path.join(BARCODE_FOLDER, f"temp_barcode_{barcode_value}.png")
                            saved_path = code.save(filename, options)
                            
                            # تحميل صورة الباركود
                            barcode_img = QImage(saved_path)
                            if barcode_img.isNull():
                                raise ValueError("فشل تحميل صورة الباركود")
                            
                            # حساب أبعاد الباركود على الصفحة
                            img_width = printer.pageRect().width() * 0.9
                            img_height = img_width * (options['module_height'] / (options['module_width'] * len(barcode_value)))
                            
                            # تحديد موقع الباركود (في وسط الصفحة)
                            barcode_x = (printer.pageRect().width() - img_width) / 2
                            barcode_y = printer.pageRect().height() * 0.1  # 10% من ارتفاع الصفحة
                            
                            # رسم الباركود
                            target_rect = QRectF(barcode_x, barcode_y, img_width, img_height)
                            painter.drawImage(target_rect, barcode_img)
                            
                            # إعداد الخط لاسم المنتج
                            font = QFont()
                            font.setPointSize(name_font_size)
                            font.setBold(True)
                            painter.setFont(font)
                            
                            # اسم المنتج (أسفل الباركود)
                            product_rect = QRectF(10, barcode_y + img_height + 5, 
                                                printer.pageRect().width() - 20, 30)
                            painter.drawText(product_rect, Qt.AlignCenter, product_name)
                            
                            # السعر (إذا كان مفعل)
                            if self.show_price.isChecked():
                                price_rect = QRectF(10, barcode_y + img_height + 25, 
                                                   printer.pageRect().width() - 20, 30)
                                font.setPointSize(price_font_size)
                                painter.setFont(font)
                                painter.drawText(price_rect, Qt.AlignCenter, f"Prix : {product_price:,.2f} DA")
                            
                            # إذا لم تكن هذه هي النسخة الأخيرة من الباركود الحالي، نضيف صفحة جديدة
                            if _ < copies - 1 or (barcode_value, copies) != barcodes_to_print[-1]:
                                printer.newPage()
                            
                            # حذف الملف المؤقت
                            try:
                                os.remove(saved_path)
                            except:
                                pass
                
                except Exception as e:
                    QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء الطباعة: {str(e)}")
                finally:
                    painter.end()
            
            parent_dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء معالجة الباركود: {str(e)}")

    def print_price(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "⚠️", "يرجى تحديد منتج.")
            return
            
        price = self.table.item(row, 3).text()
        name = self.table.item(row, 0).text()
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.Custom)
        printer.setPaperSize(QSizeF(50, 30), QPrinter.Millimeter)  # حجم ورقة الطابعة الحرارية (50x30 مم)
        printer.setFullPage(True)
        
        if QPrintDialog(printer, self).exec_() == QPrintDialog.Accepted:
            painter = QPainter()
            if not painter.begin(printer):
                QMessageBox.warning(self, "خطأ", "فشل في بدء الطباعة")
                return
                
            try:
                # حساب أبعاد الصفحة
                page_rect = printer.pageRect()
                
                # إعداد الخط للسعر
                font = QFont()
                font.setPointSize(16)
                font.setBold(True)
                painter.setFont(font)
                
                # طباعة السعر في وسط الصفحة
                price_rect = QRectF(0, 0, page_rect.width(), page_rect.height() * 0.7)
                painter.drawText(price_rect, Qt.AlignCenter | Qt.AlignVCenter, f"{price} DA")
                
                # طباعة اسم المنتج في أسفل الصفحة
                font.setPointSize(12)
                font.setBold(False)
                painter.setFont(font)
                name_rect = QRectF(0, page_rect.height() * 0.7, page_rect.width(), 30)
                painter.drawText(name_rect, Qt.AlignCenter, name)
                
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء الطباعة: {str(e)}")
            finally:
                painter.end()

    def import_from_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "📥 استيراد CSV", "", "CSV Files (*.csv)")
        if not path:
            return
            
        if not self.check_db_connection():
            return
            
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)  # قراءة رأس الجدول
                
                # تحديد مواقع الأعمدة بناءً على الرأس
                try:
                    name_col = headers.index("name")
                    qty_col = headers.index("quantity")
                    purchase_col = headers.index("purchase_price")
                    sale_col = headers.index("sale_price")
                    expiry_col = headers.index("expiry_date") if "expiry_date" in headers else -1
                    barcode_col = headers.index("barcode") if "barcode" in headers else -1
                    supplier_name_col = headers.index("supplier_name") if "supplier_name" in headers else -1
                    supplier_phone_col = headers.index("supplier_phone") if "supplier_phone" in headers else -1
                except ValueError as e:
                    QMessageBox.warning(self, "خطأ في تنسيق الملف", "الملف لا يحتوي على العناوين المطلوبة")
                    return
                
                imported_count = 0
                error_count = 0
                
                for row_num, row in enumerate(reader, start=2):  # بدء العد من الصف 2 (بعد الرأس)
                    if len(row) < 4:  # يجب أن تحتوي على الأقل على الأعمدة الأساسية
                        error_count += 1
                        continue
                        
                    try:
                        # قراءة البيانات من الصف
                        name = row[name_col].strip()
                        qty = row[qty_col].strip()
                        purchase = row[purchase_col].strip()
                        sale = row[sale_col].strip()
                        
                        # قراءة الحقول الاختيارية
                        expiry = row[expiry_col].strip() if expiry_col != -1 and len(row) > expiry_col else ""
                        barcode_value = row[barcode_col].strip() if barcode_col != -1 and len(row) > barcode_col else ""
                        supplier_name = row[supplier_name_col].strip() if supplier_name_col != -1 and len(row) > supplier_name_col else ""
                        supplier_phone = row[supplier_phone_col].strip() if supplier_phone_col != -1 and len(row) > supplier_phone_col else ""
                        
                        # التحقق من البيانات الأساسية
                        if not all([name, qty, purchase, sale]):
                            error_count += 1
                            continue
                            
                        # تحويل الأنواع
                        q_val = int(qty.replace(",", ""))
                        p_val = float(purchase.replace(",", ""))
                        s_val = float(sale.replace(",", ""))
                        
                        # التحقق من القيم
                        if q_val < 0 or p_val <= 0 or s_val <= 0:
                            error_count += 1
                            continue
                            
                        # معالجة تاريخ الصلاحية إذا كان موجوداً
                        if expiry:
                            try:
                                # تحويل تاريخ الصلاحية إلى تنسيق YYYY-MM-DD
                                expiry_date = datetime.strptime(expiry, "%d/%m/%Y").strftime("%Y-%m-%d")
                            except ValueError:
                                try:
                                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").strftime("%Y-%m-%d")
                                except ValueError:
                                    expiry_date = ""
                        else:
                            expiry_date = ""
                            
                        # إنشاء باركود إذا لم يكن موجوداً
                        if not barcode_value:
                            last_id = self.cursor.execute("SELECT MAX(id) FROM products").fetchone()[0] or 0
                            barcode_value = f"CB{str(last_id + 1).zfill(8)}"
                            
                        # إدخال البيانات في قاعدة البيانات
                        self.cursor.execute(
                            "INSERT INTO products (name, quantity, purchase_price, sale_price, expiry_date, barcode, supplier_name, supplier_phone)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                            (name, q_val, p_val, s_val, expiry_date, barcode_value, supplier_name, supplier_phone)
                        )
                        imported_count += 1
                        
                    except (ValueError, IndexError, sqlite3.IntegrityError) as e:
                        error_count += 1
                        continue
                        
                self.conn.commit()
                self.load_products()
                
                msg = f"تم استيراد {imported_count} منتج بنجاح."
                if error_count > 0:
                    msg += f"\nتم تخطي {error_count} صف بسبب أخطاء في البيانات."
                QMessageBox.information(self, "✅", msg)
                
        except Exception as e:
            QMessageBox.critical(self, "❌", f"حدث خطأ أثناء الاستيراد: {str(e)}")

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "📤 تصدير CSV", "products.csv", "CSV Files (*.csv)")
        if not path:
            return
            
        if not self.check_db_connection():
            return
            
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["name", "quantity", "purchase_price", "sale_price",
                               "expiry_date", "barcode", "supplier_name", "supplier_phone"])
                
                exported_count = 0
                for row in self.cursor.execute(
                    "SELECT name, quantity, purchase_price, sale_price, expiry_date, barcode, supplier_name, supplier_phone FROM products"
                ):
                    writer.writerow(row)
                    exported_count += 1
                    
            QMessageBox.information(self, "✅", f"تم تصدير {exported_count} منتج بنجاح.")
        except Exception as e:
            QMessageBox.critical(self, "❌", f"حدث خطأ أثناء التصدير: {str(e)}")

    def closeEvent(self, event):
        try:
            if hasattr(self, 'conn') and self.conn:
                if hasattr(self.conn, '_isclosed') and not self.conn._isclosed:
                    self.conn.close()
        except Exception as e:
            QMessageBox.warning(self, "تحذير", f"حدث خطأ أثناء إغلاق الاتصال بقاعدة البيانات: {str(e)}")
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProductManagementInterface()
    window.show()
    sys.exit(app.exec_())