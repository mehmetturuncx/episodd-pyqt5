from PyQt5 import QtCore
from dotenv import parser
import sys
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QGridLayout, QScrollArea, QMessageBox, QTabWidget,
                             QDialog, QComboBox, QTextEdit, QDesktopWidget, QGroupBox, QFormLayout, QStackedWidget, QFrame, QCheckBox, QAction)
from PyQt5.QtGui import QPixmap, QFont, QCursor
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, QRect, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QSettings
from api_manager import MovieAPI
from database import DatabaseManager
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QBrush, QRegion
import qtawesome as qta

def make_circular_pixmap(veri, size=80):
    pixmap = QPixmap()
    if not pixmap.loadFromData(veri) or pixmap.isNull():
        return None
        
    pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    
    target = QPixmap(size, size)
    target.fill(Qt.transparent)
    
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    
    x = (size - pixmap.width()) // 2
    y = (size - pixmap.height()) // 2
    painter.drawPixmap(x, y, pixmap)
    painter.end()
    
    return target



class PosterLoader(QThread):
    poster_downloaded = pyqtSignal(bytes)
    
    def __init__(self, api, poster_path, parent=None):
        super().__init__(parent)
        self.api = api
        self.poster_path = poster_path
        
    def run(self):
        resim_verisi = self.api.poster_indir(self.poster_path)
        if resim_verisi:
            self.poster_downloaded.emit(resim_verisi)

class DataLoader(QThread):
    data_loaded = pyqtSignal(list, list, list)
    
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        
    def run(self):
        yeni = self.api.yeni_cikan_filmler()
        top_f = self.api.en_yuksek_puanli_filmler()
        top_d = self.api.en_yuksek_puanli_diziler()
        self.data_loaded.emit(yeni or [], top_f or [], top_d or [])

class SearchLoader(QThread):
    search_completed = pyqtSignal(list)
    
    def __init__(self, api, query, parent=None):
        super().__init__(parent)
        self.api = api
        self.query = query
        
    def run(self):
        sonuclar = self.api.film_ara(self.query)
        self.search_completed.emit(sonuclar or [])

class CreditLoader(QThread):
    credits_loaded = pyqtSignal(dict, list, list)
    
    def __init__(self, api, film_id, media_type, parent=None):
        super().__init__(parent)
        self.api = api
        self.film_id = film_id
        self.media_type = media_type
        
    def run(self):
        details, cast, directors = self.api.film_detay_ve_kredileri(self.film_id, self.media_type)
        self.credits_loaded.emit(details, cast, directors)

class StarRatingWidget(QWidget):
    ratingChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._rating = 0.0
        self._hover_rating = 0.0
        self.setFixedSize(200, 40)
        self.setCursor(Qt.PointingHandCursor)

    def value(self):
        return self._rating

    def setValue(self, val):
        self._rating = float(val)
        self.update()

    def mouseMoveEvent(self, e):
        x = e.x()
        star_width = self.width() / 5
        val = (x / star_width)
        rounded = round(val * 2) / 2
        if rounded < 0.5: rounded = 0.5
        if rounded > 5.0: rounded = 5.0
        self._hover_rating = rounded
        self.update()

    def leaveEvent(self, e):
        self._hover_rating = 0.0
        self.update()

    def mousePressEvent(self, e):
        self._rating = self._hover_rating
        self.ratingChanged.emit(self._rating)
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        val = self._hover_rating if self._hover_rating > 0 else self._rating
        
        font = QFont("Segoe UI", 28)
        painter.setFont(font)
        
        star_width = self.width() / 5
        for i in range(5):
            rect = QRect(int(i * star_width), 0, int(star_width), self.height())
            
            if val >= i + 1:
                painter.setPen(QColor("#f5c518"))
                painter.drawText(rect, Qt.AlignCenter, "★")
            elif val >= i + 0.5:
                painter.setPen(QColor("#555555"))
                painter.drawText(rect, Qt.AlignCenter, "★")
                
                painter.save()
                clip_rect = QRect(rect.left(), rect.top(), int(rect.width() / 2), rect.height())
                painter.setClipRect(clip_rect)
                painter.setPen(QColor("#f5c518"))
                painter.drawText(rect, Qt.AlignCenter, "★")
                painter.restore()
            else:
                painter.setPen(QColor("#555555"))
                painter.drawText(rect, Qt.AlignCenter, "★")

class CustomTitleBar(QWidget):
    """Custom window title bar for frameless windows."""
    def __init__(self, parent_window, title="episodd", show_minimize=True, show_maximize=True):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self._pressing = False
        self._start_pos = None
        self._has_maximize = show_maximize

        self.setFixedHeight(38)
        self.setObjectName("CustomTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(16, 16))
        self.icon_label.setFixedSize(22, 22)
        self.icon_label.setObjectName("TitleBarIcon")
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(f"  {title}")
        self.title_label.setObjectName("TitleBarText")
        layout.addWidget(self.title_label)

        layout.addStretch()

        if show_minimize:
            self.btn_min = QPushButton("─")
            self.btn_min.setObjectName("TitleBtn")
            self.btn_min.setFixedSize(46, 30)
            self.btn_min.setCursor(QCursor(Qt.PointingHandCursor))
            self.btn_min.clicked.connect(self.parent_window.showMinimized)
            layout.addWidget(self.btn_min)

        if show_maximize:
            self.btn_max = QPushButton("□")
            self.btn_max.setObjectName("TitleBtn")
            self.btn_max.setFixedSize(46, 30)
            self.btn_max.setCursor(QCursor(Qt.PointingHandCursor))
            self.btn_max.clicked.connect(self._toggle_maximize)
            layout.addWidget(self.btn_max)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("TitleCloseBtn")
        self.btn_close.setFixedSize(46, 30)
        self.btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_close.clicked.connect(self.parent_window.close)
        layout.addWidget(self.btn_close)

    def set_title(self, title):
        self.title_label.setText(f"  {title}")

    def _toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()
        self._update_max_btn()

    def _update_max_btn(self):
        if self._has_maximize and hasattr(self, 'btn_max'):
            self.btn_max.setText("❐" if self.parent_window.isMaximized() else "□")

    def mouseDoubleClickEvent(self, event):
        if self._has_maximize and event.button() == Qt.LeftButton:
            self._toggle_maximize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressing = True
            self._start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self._pressing and self._start_pos:
            if self.parent_window.isMaximized():
                old_w = self.parent_window.width()
                self.parent_window.showNormal()
                self._update_max_btn()
                new_w = self.parent_window.width()
                ratio = self._start_pos.x() / max(old_w, 1)
                new_x = event.globalPos().x() - int(new_w * ratio)
                self.parent_window.move(max(0, new_x), max(0, event.globalPos().y() - 19))
                self._start_pos = event.globalPos()
            else:
                delta = event.globalPos() - self._start_pos
                self.parent_window.move(
                    self.parent_window.x() + delta.x(),
                    self.parent_window.y() + delta.y()
                )
                self._start_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self._pressing = False
        self._start_pos = None


class ResizeFrame(QWidget):
    """Invisible edge frame for window resize in frameless mode."""
    GRIP = 5

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")
        self._direction = 0
        self._pressing = False
        self._start_pos = None
        self._start_geo = None

    def update_frame(self):
        w = self.parent_window.width()
        h = self.parent_window.height()
        self.setGeometry(0, 0, w, h)
        if self.parent_window.isMaximized():
            self.hide()
        else:
            g = self.GRIP
            tb = 38
            region = QRegion()
            region += QRegion(0, tb, g, h - tb)
            region += QRegion(w - g, tb, g, h - tb)
            region += QRegion(0, h - g, w, g)
            self.setMask(region)
            self.show()
            self.raise_()

    def _get_direction(self, pos):
        x, y = pos.x(), pos.y()
        w = self.parent_window.width()
        h = self.parent_window.height()
        g = self.GRIP
        d = 0
        if x < g: d |= 1
        if x > w - g: d |= 2
        if y > h - g: d |= 8
        return d

    def _get_cursor(self, d):
        return {
            1: Qt.SizeHorCursor, 2: Qt.SizeHorCursor,
            8: Qt.SizeVerCursor,
            9: Qt.SizeBDiagCursor, 10: Qt.SizeFDiagCursor,
        }.get(d, Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._direction = self._get_direction(event.pos())
            if self._direction:
                self._pressing = True
                self._start_pos = event.globalPos()
                self._start_geo = self.parent_window.geometry()

    def mouseMoveEvent(self, event):
        if self._pressing and self._start_geo:
            delta = event.globalPos() - self._start_pos
            geo = QRect(self._start_geo)
            min_w = max(self.parent_window.minimumWidth(), 400)
            min_h = max(self.parent_window.minimumHeight(), 300)
            if self._direction & 1:
                new_left = geo.left() + delta.x()
                if geo.right() - new_left + 1 >= min_w:
                    geo.setLeft(new_left)
            if self._direction & 2:
                new_right = geo.right() + delta.x()
                if new_right - geo.left() + 1 >= min_w:
                    geo.setRight(new_right)
            if self._direction & 8:
                new_bottom = geo.bottom() + delta.y()
                if new_bottom - geo.top() + 1 >= min_h:
                    geo.setBottom(new_bottom)
            self.parent_window.setGeometry(geo)
        else:
            d = self._get_direction(event.pos())
            self.setCursor(self._get_cursor(d))

    def mouseReleaseEvent(self, event):
        self._pressing = False
        self._direction = 0


class CustomInputDialog(QDialog):
    def __init__(self, title, label_text, is_password=False, default_text="", is_double_password=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(380, 290 if is_double_password else 240)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        self.setObjectName("CustomDialog")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)
        outer_layout.setSpacing(0)

        self.dialog_title_bar = CustomTitleBar(self, title, show_minimize=False, show_maximize=False)
        self.dialog_title_bar.setFixedHeight(32)
        outer_layout.addWidget(self.dialog_title_bar)

        content = QWidget()
        content.setObjectName("DialogContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 10, 20, 20)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 14px; background: transparent;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.input1 = QLineEdit()
        self.input1.setText(default_text)
        if is_password:
            self.input1.setEchoMode(QLineEdit.Password)
        self.input1.setFixedHeight(40)
        layout.addWidget(self.input1)

        self.is_double_password = is_double_password
        if is_double_password:
            self.input2 = QLineEdit()
            self.input2.setPlaceholderText("Şifreyi tekrar girin")
            self.input2.setEchoMode(QLineEdit.Password)
            self.input2.setFixedHeight(40)
            layout.addWidget(self.input2)

        btn_layout = QHBoxLayout()
        kaydet = QPushButton("Onayla")
        kaydet.setObjectName("PrimaryButon")
        kaydet.setFixedHeight(40)
        kaydet.setCursor(QCursor(Qt.PointingHandCursor))

        iptal = QPushButton("İptal")
        iptal.setFixedHeight(40)
        iptal.setCursor(QCursor(Qt.PointingHandCursor))

        kaydet.clicked.connect(self.accept)
        iptal.clicked.connect(self.reject)

        btn_layout.addWidget(iptal)
        btn_layout.addWidget(kaydet)
        layout.addLayout(btn_layout)

        outer_layout.addWidget(content)

    def get_texts(self):
        if self.is_double_password:
            return self.input1.text(), self.input2.text()
        return self.input1.text()

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 episodd")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(600, 500)

        self.settings = QSettings("episodd", "AppConfig")
        self.db = DatabaseManager()
        self.arayuzu_hazirla()
        self.ayarlari_yukle()
        self.temayi_uygula()

        self.resize_frame = ResizeFrame(self)
        self.showMaximized()

    def center(self):
        pass

    def ayarlari_yukle(self):
        saved_user = self.settings.value("saved_username", "")
        saved_pass = self.settings.value("saved_password", "")
        remember_me = self.settings.value("remember_me", False, type=bool)

        if remember_me:
            self.beni_hatirla_cb.setChecked(True)
            self.kullanici_input.setText(saved_user)
            self.sifre_input.setText(saved_pass)

    def sifre_gorunurluk_degistir(self):
        if self.sifre_input.echoMode() == QLineEdit.Password:
            self.sifre_input.setEchoMode(QLineEdit.Normal)
            self.sifre_action.setIcon(qta.icon('fa5s.eye-slash', color='#aaaaaa'))
        else:
            self.sifre_input.setEchoMode(QLineEdit.Password)
            self.sifre_action.setIcon(qta.icon('fa5s.eye', color='#aaaaaa'))

    def arayuzu_hazirla(self):
        merkez = QFrame()
        merkez.setObjectName("MerkezWidget")
        self.setCentralWidget(merkez)
        ana_layout = QVBoxLayout(merkez)
        ana_layout.setContentsMargins(0, 0, 0, 0)
        ana_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = CustomTitleBar(self, "🎬 episodd")
        ana_layout.addWidget(self.title_bar)

        ana_layout.addStretch(1)
        
        self.form_container = QFrame()
        self.form_container.setObjectName("FormContainer")
        self.form_container.setFixedSize(500, 550)
        
        form_layout = QVBoxLayout(self.form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked = QStackedWidget()
        self.stacked.setObjectName("StackedWidget")
        form_layout.addWidget(self.stacked)
        
        ana_layout.addWidget(self.form_container, 0, Qt.AlignHCenter)

        ana_layout.addStretch(1)
        
        # --- LOGIN SAYFASI ---
        login_widget = QWidget()
        login_widget.setObjectName("LoginWidget")
        l_layout = QVBoxLayout(login_widget)
        l_layout.setAlignment(Qt.AlignCenter)
        
        logo_label = QLabel()
        logo_label.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(72, 72))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("margin-bottom: 10px; background: transparent;")
        l_layout.addWidget(logo_label)

        baslik = QLabel("episodd")
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 40px; color: #ffffff; background: transparent;")
        l_layout.addWidget(baslik)

        self.kullanici_input = QLineEdit()
        self.kullanici_input.setPlaceholderText("Kullanıcı Adı")
        self.kullanici_input.setFixedWidth(320)
        self.kullanici_input.setFixedHeight(50)
        l_layout.addWidget(self.kullanici_input, alignment=Qt.AlignHCenter)

        self.sifre_input = QLineEdit()
        self.sifre_input.setPlaceholderText("Şifre")
        self.sifre_input.setEchoMode(QLineEdit.Password)
        self.sifre_input.setFixedWidth(320)
        self.sifre_input.setFixedHeight(50)
        
        self.sifre_action = self.sifre_input.addAction(qta.icon('fa5s.eye', color='#aaaaaa'), QLineEdit.TrailingPosition)
        self.sifre_action.triggered.connect(self.sifre_gorunurluk_degistir)
        
        l_layout.addWidget(self.sifre_input, alignment=Qt.AlignHCenter)

        self.beni_hatirla_cb = QCheckBox("Beni Hatırla")
        self.beni_hatirla_cb.setStyleSheet("color: #aaaaaa; background: transparent; font-size: 14px; margin-bottom: 10px; margin-top: 5px;")
        self.beni_hatirla_cb.setFixedWidth(320)
        self.beni_hatirla_cb.setCursor(QCursor(Qt.PointingHandCursor))
        l_layout.addWidget(self.beni_hatirla_cb, alignment=Qt.AlignHCenter)

        self.giris_butonu = QPushButton("Giriş Yap")
        self.giris_butonu.setFixedSize(320, 50)
        self.giris_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.giris_butonu.clicked.connect(self.giris_kontrol)
        l_layout.addWidget(self.giris_butonu, alignment=Qt.AlignHCenter)
        
        gecis_layout = QHBoxLayout()
        gecis_lbl = QLabel("Hesabın yok mu?")
        gecis_lbl.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.kayda_gec_btn = QPushButton("Kayıt Ol")
        self.kayda_gec_btn.setStyleSheet("color: #e50914; background: transparent; font-weight: bold; border: none;")
        self.kayda_gec_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.kayda_gec_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        
        gecis_layout.addStretch()
        gecis_layout.addWidget(gecis_lbl)
        gecis_layout.addWidget(self.kayda_gec_btn)
        gecis_layout.addStretch()
        l_layout.addLayout(gecis_layout)
        
        self.stacked.addWidget(login_widget)
        
        # --- KAYIT SAYFASI ---
        kayit_widget = QWidget()
        kayit_widget.setObjectName("KayitWidget")
        k_layout = QVBoxLayout(kayit_widget)
        k_layout.setAlignment(Qt.AlignCenter)
        
        k_logo_label = QLabel()
        k_logo_label.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(72, 72))
        k_logo_label.setAlignment(Qt.AlignCenter)
        k_logo_label.setStyleSheet("margin-bottom: 10px; background: transparent;")
        k_layout.addWidget(k_logo_label)

        k_baslik = QLabel("Kayıt Ol")
        k_baslik.setAlignment(Qt.AlignCenter)
        k_baslik.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 40px; color: #ffffff; background: transparent;")
        k_layout.addWidget(k_baslik)

        self.k_kullanici_input = QLineEdit()
        self.k_kullanici_input.setPlaceholderText("Kullanıcı Adı")
        self.k_kullanici_input.setFixedWidth(320)
        self.k_kullanici_input.setFixedHeight(50)
        k_layout.addWidget(self.k_kullanici_input, alignment=Qt.AlignHCenter)

        self.k_sifre_input = QLineEdit()
        self.k_sifre_input.setPlaceholderText("Şifre")
        self.k_sifre_input.setEchoMode(QLineEdit.Password)
        self.k_sifre_input.setFixedWidth(320)
        self.k_sifre_input.setFixedHeight(50)
        k_layout.addWidget(self.k_sifre_input, alignment=Qt.AlignHCenter)
        
        self.k_sifre_tekrar = QLineEdit()
        self.k_sifre_tekrar.setPlaceholderText("Şifre (Tekrar)")
        self.k_sifre_tekrar.setEchoMode(QLineEdit.Password)
        self.k_sifre_tekrar.setFixedWidth(320)
        self.k_sifre_tekrar.setFixedHeight(50)
        k_layout.addWidget(self.k_sifre_tekrar, alignment=Qt.AlignHCenter)

        self.kayit_butonu = QPushButton("Kayıt İşlemini Tamamla")
        self.kayit_butonu.setFixedSize(320, 50)
        self.kayit_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.kayit_butonu.clicked.connect(self.kayit_ol)
        k_layout.addWidget(self.kayit_butonu, alignment=Qt.AlignHCenter)
        
        geri_layout = QHBoxLayout()
        geri_lbl = QLabel("Zaten hesabın var mı?")
        geri_lbl.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.girise_gec_btn = QPushButton("Giriş Yap")
        self.girise_gec_btn.setStyleSheet("color: #e50914; background: transparent; font-weight: bold; border: none;")
        self.girise_gec_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.girise_gec_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        
        geri_layout.addStretch()
        geri_layout.addWidget(geri_lbl)
        geri_layout.addWidget(self.girise_gec_btn)
        geri_layout.addStretch()
        k_layout.addLayout(geri_layout)
        
        self.stacked.addWidget(kayit_widget)

    def giris_kontrol(self):
        kullanici_adi = self.kullanici_input.text()
        sifre = self.sifre_input.text()

        if not kullanici_adi or not sifre:
            QMessageBox.warning(self, "Hata", "Lütfen tüm alanları doldurun.")
            return

        self.db.cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (kullanici_adi,))
        sonuc = self.db.cursor.fetchone()

        if sonuc:
            user_id, kayitli_hash = sonuc
            girilen_hash = hashlib.sha256(sifre.encode()).hexdigest()
            
            if girilen_hash == kayitli_hash:
                if self.beni_hatirla_cb.isChecked():
                    self.settings.setValue("saved_username", kullanici_adi)
                    self.settings.setValue("saved_password", sifre)
                    self.settings.setValue("remember_me", True)
                else:
                    self.settings.setValue("saved_username", "")
                    self.settings.setValue("saved_password", "")
                    self.settings.setValue("remember_me", False)
                    
                self.ana_pencere = MovieApp(kullanici_adi, user_id, self.db)
                self.ana_pencere.showMaximized()
                self.close()
            else:
                QMessageBox.critical(self, "Hata", "Şifre yanlış!")
        else:
            QMessageBox.critical(self, "Hata", "Kullanıcı bulunamadı!")

    def kayit_ol(self):
        kullanici_adi = self.k_kullanici_input.text()
        sifre = self.k_sifre_input.text()
        sifre_tekrar = self.k_sifre_tekrar.text()

        if not kullanici_adi or not sifre or not sifre_tekrar:
            QMessageBox.warning(self, "Hata", "Lütfen tüm alanları doldurun.")
            return

        if sifre != sifre_tekrar:
            QMessageBox.warning(self, "Hata", "Şifreler eşleşmiyor.")
            return

        if self.db.kullanici_ekle(kullanici_adi, sifre):
            QMessageBox.information(self, "Başarılı", "Kayıt oldunuz! Şimdi giriş yapabilirsiniz.")
            self.stacked.setCurrentIndex(0)
            self.kullanici_input.setText(kullanici_adi)
            self.sifre_input.clear()
            self.k_kullanici_input.clear()
            self.k_sifre_input.clear()
            self.k_sifre_tekrar.clear()
        else:
            QMessageBox.warning(self, "Hata", "Bu kullanıcı adı zaten alınmış.")

    def temayi_uygula(self):
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        bg_path = os.path.join(base_dir, "episoddBackground.png").replace("\\", "/")
        
        koyu_stil = f"""
        QMainWindow {{
            background: #0f0f17;
        }}
        #MerkezWidget {{
            border-image: url("{bg_path}") 0 0 0 0 stretch stretch;
        }}
        #FormContainer {{
            background-color: rgba(20, 20, 30, 220);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        #StackedWidget, #LoginWidget, #KayitWidget {{
            background: transparent;
        }}
        QWidget {{
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        QLineEdit {{
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 0 15px;
            color: #FFFFFF;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        QLineEdit:focus {{
            border: 1px solid #e50914;
            background-color: rgba(255, 255, 255, 0.08);
        }}
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e50914, stop:1 #b80710);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f40612, stop:1 #e50914);
        }}
        #CustomTitleBar {{
            background-color: rgba(10, 10, 20, 230);
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }}
        #TitleBarIcon, #TitleBarText {{
            background: transparent;
        }}
        #TitleBarText {{
            font-size: 13px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.6);
        }}
        #TitleBtn {{
            background: transparent;
            border: none;
            border-radius: 0px;
            color: rgba(255, 255, 255, 0.6);
            font-size: 14px;
            font-weight: normal;
        }}
        #TitleBtn:hover {{
            background-color: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }}
        #TitleCloseBtn {{
            background: transparent;
            border: none;
            border-radius: 0px;
            color: rgba(255, 255, 255, 0.6);
            font-size: 14px;
            font-weight: normal;
        }}
        #TitleCloseBtn:hover {{
            background-color: #e81123;
            color: white;
        }}
        #CustomDialog {{
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        #DialogContent {{
            background: transparent;
        }}
        """
        self.setStyleSheet(koyu_stil)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'resize_frame'):
            self.resize_frame.update_frame()

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange:
            if hasattr(self, 'title_bar'):
                self.title_bar._update_max_btn()
            if hasattr(self, 'resize_frame'):
                self.resize_frame.update_frame()
        super().changeEvent(event)

class DegerlendirmePenceresi(QWidget):
    def __init__(self, main_app, movie_id, film_adi, poster_path=None):
        super().__init__(main_app)
        self.main_app = main_app
        self.movie_id = movie_id
        self.film_adi = film_adi
        self.poster_path = poster_path
        self.active_loaders = []
        self.arayuzu_kur()
        self.setStyleSheet(main_app.styleSheet())

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        header_h = QHBoxLayout()
        geri_btn = QPushButton(" İptal / Geri Dön")
        geri_btn.setIcon(qta.icon('fa5s.arrow-left', color='white'))
        geri_btn.setObjectName("PrimaryButon")
        geri_btn.setFixedSize(160, 40)
        geri_btn.setCursor(QCursor(Qt.PointingHandCursor))
        geri_btn.clicked.connect(lambda: self.main_app.kadro_kapat(self))
        header_h.addWidget(geri_btn)
        
        baslik = QLabel(f"Değerlendir: {self.film_adi}")
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("font-size: 24px; font-weight: bold; background: transparent;")
        header_h.addWidget(baslik)
        header_h.addStretch()
        layout.addLayout(header_h)

        self.poster_lbl = QLabel("Afiş Yükleniyor...")
        self.poster_lbl.setFixedSize(160, 240)
        self.poster_lbl.setAlignment(Qt.AlignCenter)
        self.poster_lbl.setStyleSheet("background-color: rgba(255,255,255,0.05); border-radius: 10px;")
        layout.addWidget(self.poster_lbl, alignment=Qt.AlignCenter)
        
        if self.poster_path:
            p_loader = PosterLoader(self.main_app.api, self.poster_path, self)
            self.active_loaders.append(p_loader)
            p_loader.poster_downloaded.connect(self.afis_yukle)
            p_loader.finished.connect(lambda t=p_loader: self.cleanup_thread(t))
            p_loader.start()
        else:
            self.poster_lbl.setText("Afiş Yok")

        form_v_layout = QVBoxLayout()
        form_v_layout.setAlignment(Qt.AlignTop)

        lbl_puan = QLabel("Puanın (5 Üzerinden):")
        lbl_puan.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        form_v_layout.addWidget(lbl_puan)
        
        self.puan_widget = StarRatingWidget()
        self.puan_widget.setValue(2.5)
        form_v_layout.addWidget(self.puan_widget)

        lbl_yorum = QLabel("Yorumun / Analizin:")
        lbl_yorum.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; margin-top: 15px;")
        form_v_layout.addWidget(lbl_yorum)
        
        self.yorum_kutusu = QTextEdit()
        self.yorum_kutusu.setPlaceholderText("Film hakkında ne düşünüyorsun?")
        form_v_layout.addWidget(self.yorum_kutusu)

        self.kaydet_butonu = QPushButton("Kaydet")
        self.kaydet_butonu.setObjectName("PrimaryButon")
        self.kaydet_butonu.setFixedHeight(45)
        self.kaydet_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.kaydet_butonu.clicked.connect(self.kaydet)
        form_v_layout.addWidget(self.kaydet_butonu)

        layout.addLayout(form_v_layout)

    def afis_yukle(self, veri):
        pixmap = QPixmap()
        if pixmap.loadFromData(veri):
            self.poster_lbl.setPixmap(pixmap.scaled(160, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.poster_lbl.setText("")

    def cleanup_thread(self, thread):
        if thread in self.active_loaders:
            self.active_loaders.remove(thread)
        thread.deleteLater()

    def kaydet(self):
        status = "İzlendi"
        rating = self.puan_widget.value()
        review = self.yorum_kutusu.toPlainText()
        self.main_app.db.film_degerlendir(self.main_app.user_id, self.movie_id, status, rating, review)
        
        current_tab = self.main_app.sekmeler.currentIndex()
        if current_tab == 1:
            self.main_app.izlediklerimi_guncelle()
        elif current_tab == 2:
            self.main_app.daha_sonra_izle_guncelle()
            
        self.main_app.kadro_kapat(self)

class FilmDetayPenceresi(QWidget):
    def __init__(self, main_app, film_adi, rating, review):
        super().__init__(main_app)
        self.main_app = main_app
        self.film_adi = film_adi
        self.rating = rating
        self.review = review
        self.arayuzu_kur()
        self.setStyleSheet(main_app.styleSheet())

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        header_h = QHBoxLayout()
        geri_btn = QPushButton(" Geri Dön")
        geri_btn.setIcon(qta.icon('fa5s.arrow-left', color='white'))
        geri_btn.setObjectName("PrimaryButon")
        geri_btn.setFixedSize(120, 40)
        geri_btn.setCursor(QCursor(Qt.PointingHandCursor))
        geri_btn.clicked.connect(lambda: self.main_app.kadro_kapat(self))
        header_h.addWidget(geri_btn)
        
        baslik = QLabel(self.film_adi)
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("font-size: 24px; font-weight: bold; background: transparent;")
        header_h.addWidget(baslik)
        header_h.addStretch()
        layout.addLayout(header_h)

        ayirici = QWidget()
        ayirici.setFixedHeight(2)
        ayirici.setStyleSheet("background-color: rgba(255,255,255,0.1); margin: 15px 0;")
        layout.addWidget(ayirici)

        lbl_puan = QLabel("Verdiğin Puan:")
        lbl_puan.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; margin-top: 5px;")
        layout.addWidget(lbl_puan)

        puan_widget = StarRatingWidget()
        puan_widget.setValue(float(self.rating) if self.rating else 0)
        puan_widget.setEnabled(False)
        layout.addWidget(puan_widget)

        puan_text = QLabel(f"{float(self.rating):.1f} / 5.0" if self.rating else "Puanlanmadı")
        puan_text.setStyleSheet("font-size: 15px; color: #f5c518; background: transparent;")
        layout.addWidget(puan_text)

        lbl_yorum = QLabel("Yorumun:")
        lbl_yorum.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; margin-top: 10px;")
        layout.addWidget(lbl_yorum)

        yorum_kutusu = QTextEdit()
        yorum_kutusu.setReadOnly(True)
        yorum_kutusu.setText(self.review if self.review else "Henüz yorum yazılmamış.")
        yorum_kutusu.setStyleSheet("font-size: 15px; font-style: italic;")
        layout.addWidget(yorum_kutusu)
        layout.addStretch()

class FilmKadroPenceresi(QWidget):
    def __init__(self, main_app, film_dict):
        super().__init__(main_app)
        self.main_app = main_app
        self.film = film_dict
        self.setStyleSheet(main_app.styleSheet())
        self.active_loaders = []
        
        self.arayuzu_kur()
        self.kadroyu_yukle()
        
    def arayuzu_kur(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(30, 30, 30, 30)
        
        # Geri Dön Butonu
        header_h = QHBoxLayout()
        geri_btn = QPushButton(" Geri Dön")
        geri_btn.setIcon(qta.icon('fa5s.arrow-left', color='white'))
        geri_btn.setObjectName("PrimaryButon")
        geri_btn.setFixedSize(120, 40)
        geri_btn.setCursor(QCursor(Qt.PointingHandCursor))
        geri_btn.clicked.connect(lambda: self.main_app.kadro_kapat(self))
        header_h.addWidget(geri_btn)
        header_h.addStretch()
        self.layout.addLayout(header_h)
        
        # Üst Kısım: Poster ve Detaylar
        self.top_h_layout = QHBoxLayout()
        self.top_h_layout.setSpacing(30)
        
        # Sol: Poster
        self.poster_lbl = QLabel("Afiş Yükleniyor...")
        self.poster_lbl.setFixedSize(250, 375)
        self.poster_lbl.setAlignment(Qt.AlignCenter)
        self.poster_lbl.setStyleSheet("background-color: rgba(255,255,255,0.05); border-radius: 10px;")
        self.top_h_layout.addWidget(self.poster_lbl)
        
        # Sağ: Detaylar
        self.detay_v_layout = QVBoxLayout()
        self.detay_v_layout.setAlignment(Qt.AlignTop)
        self.detay_v_layout.setSpacing(15)
        
        self.baslik_lbl = QLabel("")
        self.baslik_lbl.setWordWrap(True)
        self.baslik_lbl.setStyleSheet("font-size: 32px; font-weight: bold; background: transparent;")
        self.detay_v_layout.addWidget(self.baslik_lbl)
        
        self.info_lbl = QLabel("Bilgiler Yükleniyor...")
        self.info_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #aaa; background: transparent;")
        self.detay_v_layout.addWidget(self.info_lbl)
        
        self.overview_scroll = QScrollArea()
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setFrameShape(QScrollArea.NoFrame)
        self.overview_scroll.setStyleSheet("background: transparent;")
        
        self.overview_lbl = QLabel("Açıklama Yükleniyor...")
        self.overview_lbl.setWordWrap(True)
        self.overview_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.overview_lbl.setStyleSheet("font-size: 16px; color: #e0e0e0; line-height: 1.5; background: transparent; padding-right: 15px;")
        self.overview_scroll.setWidget(self.overview_lbl)
        
        self.detay_v_layout.addWidget(self.overview_scroll)
        
        # Action Buttons
        self.actions_layout = QHBoxLayout()
        
        self.btn_daha_sonra = QPushButton(" Daha Sonra İzle")
        self.btn_daha_sonra.setIcon(qta.icon('fa5s.clock', color='white'))
        self.btn_daha_sonra.setObjectName("SecondaryButon")
        self.btn_daha_sonra.setFixedSize(160, 40)
        self.btn_daha_sonra.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_daha_sonra.clicked.connect(self.daha_sonra_izle_ekle)
        self.actions_layout.addWidget(self.btn_daha_sonra)
        
        self.btn_degerlendir = QPushButton(" Değerlendir")
        self.btn_degerlendir.setIcon(qta.icon('fa5s.star', color='white'))
        self.btn_degerlendir.setObjectName("PrimaryButon")
        self.btn_degerlendir.setFixedSize(140, 40)
        self.btn_degerlendir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_degerlendir.clicked.connect(self.degerlendirme_sayfasi_ac)
        self.actions_layout.addWidget(self.btn_degerlendir)
        self.actions_layout.addStretch()
        
        self.detay_v_layout.addLayout(self.actions_layout)
        
        self.yonetmen_lbl = QLabel("Yönetmen: Yükleniyor...")
        self.yonetmen_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #e50914; background: transparent; margin-top: 10px;")
        self.detay_v_layout.addWidget(self.yonetmen_lbl)
        
        self.top_h_layout.addLayout(self.detay_v_layout)
        self.layout.addLayout(self.top_h_layout)

        if self.main_app.film_listede_mi(self.film.get('id')):
            self.btn_daha_sonra.setText(" Eklendi")
            self.btn_daha_sonra.setStyleSheet("background-color: #2ecc71; color: white;")
            self.btn_daha_sonra.setEnabled(False)
        
        # Ayırıcı
        ayirici = QWidget()
        ayirici.setFixedHeight(2)
        ayirici.setStyleSheet("background-color: rgba(255,255,255,0.1); margin: 20px 0;")
        self.layout.addWidget(ayirici)
        
        # Alt Kısım: Oyuncular
        self.oyuncu_layout = QHBoxLayout()
        self.oyuncu_layout.setAlignment(Qt.AlignLeft)
        self.oyuncu_layout.setSpacing(25)
        
        oyuncu_scroll = QScrollArea()
        oyuncu_scroll.setWidgetResizable(True)
        oyuncu_scroll.setFrameShape(QScrollArea.NoFrame)
        oyuncu_scroll.setStyleSheet("background: transparent;")
        
        self.oyuncu_container = QWidget()
        self.oyuncu_container.setLayout(self.oyuncu_layout)
        self.oyuncu_container.setStyleSheet("background: transparent;")
        oyuncu_scroll.setWidget(self.oyuncu_container)
        
        self.layout.addWidget(oyuncu_scroll)
        
    def kadroyu_yukle(self):
        film_id = self.film.get('id')
        media_type = self.film.get('media_type', 'movie')
        
        self.loader = CreditLoader(self.main_app.api, film_id, media_type, self)
        self.active_loaders.append(self.loader)
        self.loader.credits_loaded.connect(self.kadroyu_goster)
        self.loader.finished.connect(lambda t=self.loader: self.cleanup_thread(t))
        self.loader.start()

        poster_path = self.film.get('poster_path')
        if poster_path:
            p_loader = PosterLoader(self.main_app.api, poster_path, self)
            self.active_loaders.append(p_loader)
            p_loader.poster_downloaded.connect(self.ana_afis_yukle)
            p_loader.finished.connect(lambda t=p_loader: self.cleanup_thread(t))
            p_loader.start()
        else:
            self.poster_lbl.setText("Afiş Yok")

    def ana_afis_yukle(self, veri):
        pixmap = QPixmap()
        if pixmap.loadFromData(veri):
            self.poster_lbl.setPixmap(pixmap.scaled(250, 375, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.poster_lbl.setText("")
        
    def kadroyu_goster(self, details, cast, directors):
        title = details.get('title') or details.get('name') or self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        self.baslik_lbl.setText(title)
        
        overview = details.get("overview", "Açıklama bulunamadı.")
        if not overview or not overview.strip(): overview = "Açıklama bulunamadı."
        vote_average = details.get("vote_average", "Bilinmiyor")
        if isinstance(vote_average, (int, float)):
            vote_average = f"{vote_average:.1f}"
        release_date = details.get("release_date") or details.get("first_air_date", "Bilinmiyor")
        
        self.info_lbl.setText(f"Puan: {vote_average} / 10  |  Çıkış Tarihi: {release_date}")
        self.overview_lbl.setText(overview)
        
        if directors:
            yonetmen_isimleri = ", ".join([d.get("name") for d in directors])
            self.yonetmen_lbl.setText(f"Yönetmen: {yonetmen_isimleri}")
            self.yonetmen_lbl.show()
        else:
            self.yonetmen_lbl.hide()
            
        for i in reversed(range(self.oyuncu_layout.count())): 
            w = self.oyuncu_layout.itemAt(i).widget()
            if w:
                self.oyuncu_layout.removeWidget(w)
                w.setParent(None)
                
        if not cast:
            lbl = QLabel("Oyuncu bilgisi bulunamadı.")
            lbl.setAlignment(Qt.AlignCenter)
            self.oyuncu_layout.addWidget(lbl)
            return
            
        for actor in cast:
            actor_widget = QWidget()
            vbox = QVBoxLayout(actor_widget)
            vbox.setAlignment(Qt.AlignCenter)
            vbox.setSpacing(5)
            
            avatar_lbl = QLabel()
            avatar_size = 100
            avatar_lbl.setFixedSize(avatar_size, avatar_size)
            avatar_lbl.setAlignment(Qt.AlignCenter)
            
            profile_path = actor.get("profile_path")
            if profile_path:
                avatar_lbl.setText("...")
                avatar_lbl.setStyleSheet("color: #888;")
                p_loader = PosterLoader(self.main_app.api, profile_path, self)
                self.active_loaders.append(p_loader)
                p_loader.poster_downloaded.connect(lambda veri, lbl=avatar_lbl, size=avatar_size: self.foto_yukle(lbl, veri, size))
                p_loader.finished.connect(lambda t=p_loader: self.cleanup_thread(t))
                p_loader.start()
            else:
                avatar_lbl.setText("Yok")
                avatar_lbl.setStyleSheet(f"border-radius: {avatar_size//2}px; background-color: #333; color: #888;")
                
            name_lbl = QLabel(actor.get("name"))
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setWordWrap(True)
            name_lbl.setFixedWidth(110)
            name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent;")
            
            char_lbl = QLabel(actor.get("character", ""))
            char_lbl.setAlignment(Qt.AlignCenter)
            char_lbl.setWordWrap(True)
            char_lbl.setFixedWidth(110)
            char_lbl.setStyleSheet("font-size: 11px; color: #aaa; background: transparent;")
            
            vbox.addWidget(avatar_lbl)
            vbox.addWidget(name_lbl)
            vbox.addWidget(char_lbl)
            vbox.addStretch()
            
            self.oyuncu_layout.addWidget(actor_widget)
            
    def foto_yukle(self, label, veri, size):
        pixmap = make_circular_pixmap(veri, size)
        if pixmap:
            label.setPixmap(pixmap)
            label.setText("")
            label.setStyleSheet("background: transparent;")
            
    def cleanup_thread(self, thread):
        if thread in self.active_loaders:
            self.active_loaders.remove(thread)
        thread.deleteLater()

    def daha_sonra_izle_ekle(self):
        user_id = self.main_app.user_id
        film_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        poster_path = self.film.get('poster_path')
        
        self.main_app.db.film_kaydet(film_id, title, poster_path)
        eklendi_mi = self.main_app.db.kullanici_film_ekle(user_id, film_id, status="İzlenecek")
        if eklendi_mi:
            self.main_app.daha_sonra_izle_guncelle()
        
        self.btn_daha_sonra.setText(" Eklendi")
        self.btn_daha_sonra.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_daha_sonra.setEnabled(False)

    def degerlendirme_sayfasi_ac(self):
        film_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        poster_path = self.film.get('poster_path')
        self.main_app.degerlendirme_ac(film_id, title, poster_path)

class HoverOverlayWidget(QWidget):
    def __init__(self, parent=None, film=None, main_app=None):
        super().__init__(parent)
        self.film = film
        self.main_app = main_app
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7); border-radius: 8px;")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.btn_izle = QPushButton(" Daha Sonra İzle")
        self.btn_izle.setIcon(qta.icon('fa5s.clock', color='white'))
        self.btn_izle.setObjectName("PrimaryButon")
        self.btn_izle.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_izle.setFixedHeight(35)
        self.btn_izle.clicked.connect(self.daha_sonra_izle)
        
        self.btn_degerlendir = QPushButton(" Değerlendir")
        self.btn_degerlendir.setIcon(qta.icon('fa5s.star', color='white'))
        self.btn_degerlendir.setObjectName("PrimaryButon")
        self.btn_degerlendir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_degerlendir.setFixedHeight(35)
        self.btn_degerlendir.clicked.connect(self.degerlendir)
        
        layout.addWidget(self.btn_izle)
        layout.addWidget(self.btn_degerlendir)
        self.hide()
        
        if self.film and self.main_app.film_listede_mi(self.film.get('id')):
            self.btn_izle.setText(" Eklendi")
            self.btn_izle.setStyleSheet("background-color: #2ecc71; color: white;")
            self.btn_izle.setEnabled(False)
        
    def daha_sonra_izle(self):
        eklendi_mi = self.main_app.listeye_ekle(self.film)
        if eklendi_mi:
            self.main_app.daha_sonra_izle_guncelle()
            
        self.btn_izle.setText(" Eklendi")
        self.btn_izle.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_izle.setEnabled(False)
        
    def degerlendir(self):
        movie_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        self.main_app.degerlendirme_ac(movie_id, title)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.main_app.kadro_goster(self.film)


class ListHoverOverlayWidget(QWidget):
    """Hover overlay for list items (İzlediklerim / Daha Sonra İzle) with Değerlendir and Kaldır buttons."""
    def __init__(self, parent=None, tmdb_id=None, title=None, main_app=None, list_type=None):
        super().__init__(parent)
        self.tmdb_id = tmdb_id
        self.title = title
        self.main_app = main_app
        self.list_type = list_type  # 'izlediklerim' or 'daha_sonra_izle'
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7); border-radius: 8px;")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.btn_degerlendir = QPushButton(" Değerlendir")
        self.btn_degerlendir.setIcon(qta.icon('fa5s.star', color='white'))
        self.btn_degerlendir.setObjectName("PrimaryButon")
        self.btn_degerlendir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_degerlendir.setFixedHeight(35)
        self.btn_degerlendir.clicked.connect(self.degerlendir)
        
        self.btn_kaldir = QPushButton(" Kaldır")
        self.btn_kaldir.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        self.btn_kaldir.setObjectName("KaldirButonu")
        self.btn_kaldir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_kaldir.setFixedHeight(35)
        self.btn_kaldir.clicked.connect(self.kaldir)
        
        layout.addWidget(self.btn_degerlendir)
        layout.addWidget(self.btn_kaldir)
        self.hide()
    
    def degerlendir(self):
        self.main_app.degerlendirme_ac(self.tmdb_id, self.title)
    
    def kaldir(self):
        self.main_app.listeden_kaldir(self.tmdb_id, self.title, self.list_type)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            film_dict = {'id': self.tmdb_id, 'title': self.title, 'media_type': 'movie'}
            self.main_app.kadro_goster(film_dict)

class CarouselWidget(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.main_app = parent
        self.filmler = []
        self.current_idx = 0
        
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignLeft)
        
        carousel_layout = QHBoxLayout()
        carousel_layout.setAlignment(Qt.AlignLeft)
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(qta.icon('fa5s.chevron-left', color='white'))
        self.btn_prev.setFixedSize(40, 40)
        self.btn_prev.setObjectName("PrimaryButon")
        self.btn_prev.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_prev.clicked.connect(self.prev_film)
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(qta.icon('fa5s.chevron-right', color='white'))
        self.btn_next.setFixedSize(40, 40)
        self.btn_next.setObjectName("PrimaryButon")
        self.btn_next.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_next.clicked.connect(self.next_film)
        
        self.poster_container = QWidget()
        self.poster_width = 715
        self.poster_height = 450
        self.poster_container.setFixedSize(self.poster_width, self.poster_height)
        
        self.afis_label = QLabel(self.poster_container)
        self.afis_label.setGeometry(0, 0, self.poster_width, self.poster_height)
        self.afis_label.setAlignment(Qt.AlignCenter)
        
        self.overlay = HoverOverlayWidget(self.poster_container, None, self.main_app)
        self.overlay.setFixedSize(self.poster_width, self.poster_height)
        self.ilerliyor = True
        
        def enter_event(e): self.overlay.show()
        def leave_event(e): self.overlay.hide()
        self.poster_container.enterEvent = enter_event
        self.poster_container.leaveEvent = leave_event
        
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.poster_container)
        
        carousel_layout.addWidget(self.btn_prev)
        carousel_layout.addLayout(center_layout)
        carousel_layout.addWidget(self.btn_next)
        
        layout.addLayout(carousel_layout)
        
        self.welcome_container = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_container)
        welcome_layout.setAlignment(Qt.AlignCenter)
        
        self.welcome_title = QLabel("Yükleniyor...")
        self.welcome_title.setStyleSheet("font-size: 26px; font-weight: bold; margin-bottom: 15px; background: transparent;")
        self.welcome_title.setAlignment(Qt.AlignCenter)
        self.welcome_title.setWordWrap(True)
        
        self.welcome_text = QLabel("")
        self.welcome_text.setWordWrap(True)
        self.welcome_text.setStyleSheet("font-size: 16px; line-height: 1.5; color: white; background: transparent;")
        self.welcome_text.setAlignment(Qt.AlignCenter)
        
        welcome_layout.addWidget(self.welcome_title)
        welcome_layout.addWidget(self.welcome_text)
        
        layout.addStretch()
        layout.addWidget(self.welcome_container)
        layout.addStretch()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_film)
        self.timer.start(5000)
        self.active_loader = None

    def set_filmler(self, filmler):
        self.filmler = filmler
        self.current_idx = 0
        
        if filmler:
            film = filmler[0]
            title = film.get('title') or film.get('name', 'Bilinmiyor')
            yil = film.get('release_date') or film.get('first_air_date', ' ')
            yil_str = yil[:4] if yil else ""
            overview = film.get('overview', '')
            if len(overview) > 400: overview = overview[:397] + "..."
            vote_average = film.get("vote_average", "Bilinmiyor")
            if isinstance(vote_average, (int, float)):
                vote_average = f"{vote_average:.1f}"
                
            self.welcome_title.setText(f"{title} ({yil_str})")
            self.welcome_text.setText(f"Puan: {vote_average} / 10\n\n{overview}")
            
        self.update_ui()
        
    def prev_film(self):
        if not self.filmler: return
        self.ilerliyor = False
        self.current_idx = (self.current_idx - 1) % len(self.filmler)
        self.update_ui()
        self.timer.start(5000)
        
    def next_film(self):
        if not self.filmler: return
        self.ilerliyor = True
        self.current_idx = (self.current_idx + 1) % len(self.filmler)
        self.update_ui()
        self.timer.start(5000)
        
    def update_ui(self):
        if not self.filmler: return
        film = self.filmler[self.current_idx]
        self.overlay.film = film
        self.overlay.hide()
        self.overlay.raise_()
        
        poster_path = film.get('poster_path')
        if poster_path:
            if not self.afis_label.pixmap():
                self.afis_label.setText("Yükleniyor...")
            
            if getattr(self, 'active_loader', None):
                try:
                    self.active_loader.poster_downloaded.disconnect()
                except (TypeError, RuntimeError):
                    pass
                    
            loader = PosterLoader(self.api, poster_path, self)
            self.main_app.active_threads.append(loader)
            loader.poster_downloaded.connect(self.afis_yukle)
            loader.finished.connect(lambda t=loader: self.main_app.cleanup_thread(t))
            loader.start()
            self.active_loader = loader
        else:
            self.afis_label.setText("Afiş Yok")
            
    def afis_yukle(self, veri):
        pixmap = QPixmap()
        if pixmap.loadFromData(veri):
            scaled_pixmap = pixmap.scaled(self.poster_width, self.poster_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            if not self.afis_label.pixmap():
                self.afis_label.setPixmap(scaled_pixmap)
                return
                
            self.new_afis_label = QLabel(self.poster_container)
            self.new_afis_label.setAlignment(Qt.AlignCenter)
            self.new_afis_label.setPixmap(scaled_pixmap)
            self.new_afis_label.resize(self.poster_width, self.poster_height)
            self.new_afis_label.show()
            self.new_afis_label.lower()
            
            direction = 1 if getattr(self, 'ilerliyor', True) else -1
            self.new_afis_label.move(direction * self.poster_width, 0)
            
            self.anim_group = QParallelAnimationGroup(self)
            
            anim1 = QPropertyAnimation(self.afis_label, b"pos", self)
            anim1.setDuration(400)
            anim1.setStartValue(self.afis_label.pos())
            anim1.setEndValue(self.afis_label.pos() + QPoint(-direction * self.poster_width, 0))
            anim1.setEasingCurve(QEasingCurve.InOutQuad)
            
            anim2 = QPropertyAnimation(self.new_afis_label, b"pos", self)
            anim2.setDuration(400)
            anim2.setStartValue(self.new_afis_label.pos())
            anim2.setEndValue(QPoint(0, 0))
            anim2.setEasingCurve(QEasingCurve.InOutQuad)
            
            self.anim_group.addAnimation(anim1)
            self.anim_group.addAnimation(anim2)
            self.anim_group.finished.connect(self.animasyon_bitti)
            self.anim_group.start()
            
    def animasyon_bitti(self):
        self.afis_label.deleteLater()
        self.afis_label = self.new_afis_label
        self.overlay.raise_()

class MovieApp(QMainWindow):
    def __init__(self, username, user_id, db_manager):
        super().__init__()
        self.username = username
        self.user_id = user_id
        self.db = db_manager 
        self.secili_tema = "Netflix" # Default tema
        
        self.setWindowTitle("episodd")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(100, 100, 1100, 850)
        self.setMinimumSize(900, 600)
        self.api = MovieAPI()
        self.active_threads = []
        
        

        self.arayuzu_hazirla()
        self.temayi_guncelle(self.secili_tema)

        self.resize_frame = ResizeFrame(self)

    

    def arayuzu_hazirla(self):
        merkez = QWidget()
        merkez.setObjectName("MovieAppMerkez")
        self.setCentralWidget(merkez)
        ana_layout = QVBoxLayout(merkez)
        ana_layout.setContentsMargins(0,0,0,0)
        ana_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = CustomTitleBar(self, "episodd")
        ana_layout.addWidget(self.title_bar)

        # 1. Üst Bar (Header)
        self.header = QWidget()
        self.header.setObjectName("Header")
        self.header.setFixedHeight(70)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 30, 0)
        
        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(30, 30))
        logo = QLabel(" episodd")
        logo.setObjectName("HeaderLogo")
        logo.setStyleSheet("font-size: 26px; font-weight: bold; background: transparent;")
        
        header_h = QHBoxLayout()
        header_h.addWidget(logo_icon)
        header_h.addWidget(logo)
        
        self.kullanici_hosgeldin = QLabel(f"Hoşgeldin, {self.username}")
        self.kullanici_hosgeldin.setObjectName("HeaderUser")
        self.kullanici_hosgeldin.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        
        header_layout.addLayout(header_h)
        header_layout.addStretch()
        header_layout.addWidget(self.kullanici_hosgeldin)

        ana_layout.addWidget(self.header)


        self.ana_stacked = QStackedWidget()
        ana_layout.addWidget(self.ana_stacked)

        self.sekmeler = QTabWidget()
        self.sekmeler.setObjectName("MainTabs")
        self.ana_stacked.addWidget(self.sekmeler)
        self.sekmeler.setStyleSheet("QTabBar::tab { width: 180px; height: 40px; }")

        self.ana_sekme = QWidget()
        self.izlediklerim_sekmesi = QWidget()
        self.daha_sonra_sekmesi = QWidget()
        self.ayarlar_sekmesi = QWidget()

        self.sekmeler.addTab(self.ana_sekme, qta.icon('fa5s.home'), " Ana Menü")
        self.sekmeler.addTab(self.izlediklerim_sekmesi, qta.icon('fa5s.check-circle'), " İzlediklerim")
        self.sekmeler.addTab(self.daha_sonra_sekmesi, qta.icon('fa5s.clock'), " Daha Sonra İzle")
        self.sekmeler.addTab(self.ayarlar_sekmesi, qta.icon('fa5s.cog'), " Ayarlar")

        self.ana_sekmesini_kur()
        self.izlediklerim_sekmesini_kur()
        self.daha_sonra_sekmesini_kur()
        self.ayarlar_sekmesini_kur()

        self.sekmeler.currentChanged.connect(self.sekme_degisti)

    def film_karti_olustur(self, film, is_large=False):
        film_kutusu = QWidget()
        width = 180
        height = 310
        film_kutusu.setFixedSize(width, height)
        film_kutusu.setObjectName("FilmKarti")
        
        kutu_layout = QVBoxLayout(film_kutusu)
        kutu_layout.setContentsMargins(8, 8, 8, 8)
        
        poster_container = QWidget()
        afis_width = 160
        afis_height = 240
        poster_container.setFixedSize(afis_width, afis_height)
        
        p_layout = QVBoxLayout(poster_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        
        afis_label = QLabel()
        afis_label.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(afis_label)
        
        overlay = HoverOverlayWidget(poster_container, film, self)
        overlay.setFixedSize(afis_width, afis_height)
        
        def enter_event(e): overlay.show()
        def leave_event(e): overlay.hide()
        poster_container.enterEvent = enter_event
        poster_container.leaveEvent = leave_event
        
        poster_path = film.get('poster_path')
        if poster_path:
            afis_label.setText("Yükleniyor...")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            loader = PosterLoader(self.api, poster_path, self)
            self.active_threads.append(loader)
            loader.poster_downloaded.connect(lambda veri, lbl=afis_label: self.afis_yukle(lbl, veri, afis_width, afis_height))
            loader.finished.connect(lambda t=loader: self.cleanup_thread(t))
            loader.start()
        else:
            afis_label.setText("Afiş Yok")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        
        yil = film.get('release_date') or film.get('first_air_date', ' ')
        yil = yil[:4]
        baslik = film.get('title') or film.get('name', 'Bilinmiyor')
        if len(baslik) > 18: baslik = baslik[:16] + "..."
        bilgi_label = QLabel(f"{baslik}\n({yil})")
        bilgi_label.setAlignment(Qt.AlignCenter)
        bilgi_label.setStyleSheet("font-size: 13px; font-weight: bold; margin-top: 4px; background: transparent;")
        
        kutu_layout.addWidget(poster_container)
        kutu_layout.addStretch()
        kutu_layout.addWidget(bilgi_label)
        return film_kutusu

    def cleanup_thread(self, thread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        thread.deleteLater()

    def afis_yukle(self, label, veri, width, height):
        pixmap = QPixmap()
        if pixmap.loadFromData(veri):
            label.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            label.setText("")

    def ana_sekmesini_kur(self):
        self.ana_layout = QVBoxLayout(self.ana_sekme)
        self.ana_layout.setContentsMargins(20, 20, 20, 20)
        
        # Arama Kısmı
        arama_layout = QHBoxLayout()
        self.arama_kutusu = QLineEdit()
        self.arama_kutusu.setPlaceholderText("Film veya dizi adı girin...")
        self.arama_kutusu.setFixedHeight(45)
        
        self.arama_butonu = QPushButton(" Ara")
        self.arama_butonu.setIcon(qta.icon('fa5s.search', color='white'))
        self.arama_butonu.setFixedSize(120, 45)
        self.arama_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.arama_butonu.setObjectName("PrimaryButon")
        self.arama_butonu.clicked.connect(self.arama_yap)
        self.arama_kutusu.returnPressed.connect(self.arama_yap)
        
        arama_layout.addWidget(self.arama_kutusu)
        arama_layout.addWidget(self.arama_butonu)
        self.ana_layout.addLayout(arama_layout)
        
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setObjectName("AnaMenuScroll")
        self.icerik_widget = QWidget()
        self.icerik_widget.setObjectName("AnaMenuIcerik")
        self.icerik_layout = QVBoxLayout(self.icerik_widget)
        
        # Arama Sonuçları (Gizli)
        self.arama_sonuc_widget = QWidget()
        self.arama_grid = QGridLayout(self.arama_sonuc_widget)
        self.arama_grid.setSpacing(15)
        self.arama_grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.arama_ust_layout = QHBoxLayout()
        self.arama_baslik = QLabel(" Arama Sonuçları")
        self.arama_baslik.setObjectName("KategoriBaslik")
        self.arama_geri_btn = QPushButton(" Geri Dön")
        self.arama_geri_btn.setIcon(qta.icon('fa5s.arrow-left', color='white'))
        self.arama_geri_btn.setObjectName("PrimaryButon")
        self.arama_geri_btn.setFixedHeight(35)
        self.arama_geri_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.arama_geri_btn.clicked.connect(self.arama_geri_don)
        self.arama_ust_layout.addWidget(self.arama_baslik)
        self.arama_ust_layout.addStretch()
        self.arama_ust_layout.addWidget(self.arama_geri_btn)
        
        self.arama_container = QWidget()
        arama_v = QVBoxLayout(self.arama_container)
        arama_v.addLayout(self.arama_ust_layout)
        arama_v.addWidget(self.arama_sonuc_widget)
        self.arama_container.hide()
        
        # Normal İçerik
        self.normal_icerik_container = QWidget()
        self.normal_icerik_layout = QVBoxLayout(self.normal_icerik_container)
        
        baslik1 = QLabel(" Yeni Çıkanlar")
        baslik1.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(baslik1)
        
        self.carousel = CarouselWidget(self.api, self)
        self.normal_icerik_layout.addWidget(self.carousel)
        
        baslik2 = QLabel(" En Yüksek Puanlı Filmler")
        baslik2.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(baslik2)
        
        top_scroll = QScrollArea()
        top_scroll.setFixedHeight(340)
        top_scroll.setWidgetResizable(True)
        top_icerik = QWidget()
        top_icerik.setObjectName("YatayIcerik")
        self.top_layout = QHBoxLayout(top_icerik)
        self.top_layout.setAlignment(Qt.AlignLeft)
        top_scroll.setWidget(top_icerik)
        self.normal_icerik_layout.addWidget(top_scroll)

        baslik3 = QLabel(" En Yüksek Puanlı Diziler")
        baslik3.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(baslik3)

        top_dizi_scroll = QScrollArea()
        top_dizi_scroll.setFixedHeight(340)
        top_dizi_scroll.setWidgetResizable(True)
        top_dizi_icerik = QWidget()
        top_dizi_icerik.setObjectName("YatayIcerik")
        self.top_dizi_layout = QHBoxLayout(top_dizi_icerik)
        self.top_dizi_layout.setAlignment(Qt.AlignLeft)
        top_dizi_scroll.setWidget(top_dizi_icerik)
        self.normal_icerik_layout.addWidget(top_dizi_scroll)
        
        self.icerik_layout.addWidget(self.normal_icerik_container)
        self.icerik_layout.addWidget(self.arama_container)
        self.main_scroll.setWidget(self.icerik_widget)
        self.ana_layout.addWidget(self.main_scroll)

        self.top_layout.addWidget(QLabel("İçerikler yükleniyor..."))
        self.top_dizi_layout.addWidget(QLabel("İçerikler yükleniyor..."))

        self.data_loader = DataLoader(self.api, self)
        self.active_threads.append(self.data_loader)
        self.data_loader.data_loaded.connect(self.ana_menu_filmleri_doldur)
        self.data_loader.finished.connect(lambda t=self.data_loader: self.cleanup_thread(t))
        self.data_loader.start()

    def ana_menu_filmleri_doldur(self, yeni_filmler, top_filmler, top_diziler):
        for i in reversed(range(self.top_layout.count())): 
            w = self.top_layout.itemAt(i).widget()
            if w: w.setParent(None)

        for i in reversed(range(self.top_dizi_layout.count())):
            w = self.top_dizi_layout.itemAt(i).widget()
            if w: w.setParent(None)

        if yeni_filmler:
            self.carousel.set_filmler(yeni_filmler)
            
        if top_filmler:
            for film in top_filmler:
                kutu = self.film_karti_olustur(film)
                self.top_layout.addWidget(kutu)
        else:
            self.top_layout.addWidget(QLabel("İçerikler yüklenemedi."))

        if top_diziler:
            for dizi in top_diziler:
                kutu = self.film_karti_olustur(dizi)
                self.top_dizi_layout.addWidget(kutu)
        else:
            self.top_dizi_layout.addWidget(QLabel("İçerikler yüklenemedi."))

    def izlediklerim_sekmesini_kur(self):
        layout = QVBoxLayout(self.izlediklerim_sekmesi)
        layout.setContentsMargins(20, 20, 20, 20)
        
        baslik = QLabel(" İzlediklerim")
        baslik.setObjectName("KategoriBaslik")
        layout.addWidget(baslik)

        self.izlediklerim_scroll = QScrollArea()
        self.izlediklerim_scroll.setWidgetResizable(True)
        self.izlediklerim_icerik = QWidget()
        self.izlediklerim_icerik.setObjectName("IcerikPaneli")
        self.izlediklerim_grid = QGridLayout(self.izlediklerim_icerik)
        self.izlediklerim_grid.setSpacing(20)
        self.izlediklerim_grid.setAlignment(Qt.AlignTop)
        self.izlediklerim_scroll.setWidget(self.izlediklerim_icerik)
        
        layout.addWidget(self.izlediklerim_scroll)

    def daha_sonra_sekmesini_kur(self):
        layout = QVBoxLayout(self.daha_sonra_sekmesi)
        layout.setContentsMargins(20, 20, 20, 20)
        
        baslik = QLabel(" Daha Sonra İzle")
        baslik.setObjectName("KategoriBaslik")
        layout.addWidget(baslik)

        self.daha_sonra_scroll = QScrollArea()
        self.daha_sonra_scroll.setWidgetResizable(True)
        self.daha_sonra_icerik = QWidget()
        self.daha_sonra_icerik.setObjectName("IcerikPaneli")
        self.daha_sonra_grid = QGridLayout(self.daha_sonra_icerik)
        self.daha_sonra_grid.setSpacing(20)
        self.daha_sonra_grid.setAlignment(Qt.AlignTop)
        self.daha_sonra_scroll.setWidget(self.daha_sonra_icerik)
        
        layout.addWidget(self.daha_sonra_scroll)

    def ayarlar_sekmesini_kur(self):
        layout = QVBoxLayout(self.ayarlar_sekmesi)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignTop)

        # Başlık
        baslik = QLabel("Hesap ve Uygulama Ayarları")
        baslik.setStyleSheet("font-size: 28px; font-weight: bold; color: white; background: transparent;")
        layout.addWidget(baslik)

        # Kullanıcı Bilgileri
        kullanici_grup = QGroupBox("Profil Bilgileri")
        kullanici_grup.setObjectName("AyarlarGrup")
        k_layout = QVBoxLayout(kullanici_grup)
        k_layout.setSpacing(15)

        self.kullanici_bilgi_lbl = QLabel(f"Mevcut Kullanıcı Adı: {self.username}")
        self.kullanici_bilgi_lbl.setStyleSheet("font-size: 16px; color: white; background: transparent;")
        k_layout.addWidget(self.kullanici_bilgi_lbl)

        btn_h = QHBoxLayout()
        k_degistir_btn = QPushButton(" Kullanıcı Adı Değiştir")
        k_degistir_btn.setIcon(qta.icon('fa5s.user-edit', color='white'))
        k_degistir_btn.setObjectName("PrimaryButon")
        k_degistir_btn.setFixedSize(220, 40)
        k_degistir_btn.setCursor(QCursor(Qt.PointingHandCursor))
        k_degistir_btn.clicked.connect(self.kullanici_adi_degistir_dialog)
        
        s_degistir_btn = QPushButton(" Şifre Değiştir")
        s_degistir_btn.setIcon(qta.icon('fa5s.key', color='white'))
        s_degistir_btn.setObjectName("PrimaryButon")
        s_degistir_btn.setFixedSize(180, 40)
        s_degistir_btn.setCursor(QCursor(Qt.PointingHandCursor))
        s_degistir_btn.clicked.connect(self.sifre_degistir_dialog)
        
        btn_h.addWidget(k_degistir_btn)
        btn_h.addWidget(s_degistir_btn)
        btn_h.addStretch()
        k_layout.addLayout(btn_h)
        
        layout.addWidget(kullanici_grup)

        # Görünüm
        gorunum_grup = QGroupBox("Görünüm Ayarları")
        gorunum_grup.setObjectName("AyarlarGrup")
        g_layout = QVBoxLayout(gorunum_grup)
        
        t_h = QHBoxLayout()
        t_lbl = QLabel("Uygulama Teması:")
        t_lbl.setStyleSheet("font-size: 16px; color: white; background: transparent;")
        
        self.ayar_tema = QComboBox()
        self.ayar_tema.addItems(["Netflix", "IMDb", "Açık Tema"])
        self.ayar_tema.setCurrentText(self.secili_tema)
        self.ayar_tema.setFixedSize(200, 40)
        self.ayar_tema.currentTextChanged.connect(self.temayi_guncelle)
        
        t_h.addWidget(t_lbl)
        t_h.addWidget(self.ayar_tema)
        t_h.addStretch()
        
        g_layout.addLayout(t_h)
        layout.addWidget(gorunum_grup)
        
        # Tehlikeli Bölge
        tehlikeli_grup = QGroupBox("Tehlikeli Bölge")
        tehlikeli_grup.setStyleSheet("QGroupBox { border: 1px solid #e50914; border-radius: 8px; margin-top: 10px; } QGroupBox::title { color: #e50914; subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
        t_layout = QVBoxLayout(tehlikeli_grup)
        t_layout.setSpacing(10)
        
        uyari_lbl = QLabel("Dikkat: Hesabınızı silmek tüm izleme geçmişinizi, puanlarınızı ve değerlendirmelerinizi kalıcı olarak siler. Bu işlem geri alınamaz.")
        uyari_lbl.setWordWrap(True)
        uyari_lbl.setStyleSheet("color: #aaaaaa; font-size: 14px; background: transparent;")
        t_layout.addWidget(uyari_lbl)
        
        sil_btn = QPushButton(" Hesabı Kalıcı Olarak Sil")
        sil_btn.setIcon(qta.icon('fa5s.exclamation-triangle', color='white'))
        sil_btn.setStyleSheet("background-color: #e50914; color: white; border-radius: 8px; font-weight: bold; padding: 0 10px;")
        sil_btn.setFixedSize(250, 45)
        sil_btn.setCursor(QCursor(Qt.PointingHandCursor))
        sil_btn.clicked.connect(self.hesap_sil_dialog)
        t_layout.addWidget(sil_btn)
        
        layout.addWidget(tehlikeli_grup)
        layout.addStretch()

    def kullanici_adi_degistir_dialog(self):
        dialog = CustomInputDialog("Kullanıcı Adı Değiştir", "Yeni Kullanıcı Adı:", default_text=self.username, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            yeni_ad = dialog.get_texts()
            if not yeni_ad:
                QMessageBox.warning(self, "Hata", "Kullanıcı adı boş olamaz.")
                return
            if self.db.kullanici_guncelle(self.user_id, yeni_ad, None):
                self.username = yeni_ad
                self.kullanici_bilgi_lbl.setText(f"Mevcut Kullanıcı Adı: {self.username}")
                self.kullanici_hosgeldin.setText(f"Hoşgeldin, {self.username}")
                QMessageBox.information(self, "Başarılı", "Kullanıcı adı güncellendi.")
            else:
                QMessageBox.warning(self, "Hata", "Bu kullanıcı adı alınmış.")

    def sifre_degistir_dialog(self):
        dialog = CustomInputDialog("Şifre Değiştir", "Yeni şifrenizi girin:", is_password=True, is_double_password=True, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            yeni_sifre, yeni_sifre_tekrar = dialog.get_texts()
            if not yeni_sifre:
                QMessageBox.warning(self, "Hata", "Şifre boş olamaz.")
                return
            if yeni_sifre == yeni_sifre_tekrar:
                self.db.kullanici_guncelle(self.user_id, self.username, yeni_sifre)
                QMessageBox.information(self, "Başarılı", "Şifre başarıyla güncellendi.")
            else:
                QMessageBox.warning(self, "Hata", "Şifreler eşleşmiyor.")

    def hesap_sil_dialog(self):
        dialog = CustomInputDialog("Hesabı Sil", "Hesabınızı silmek için şifrenizi girin:\n(Bu işlem geri alınamaz)", is_password=True, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            sifre = dialog.get_texts()
            if self.db.sifre_dogrula(self.user_id, sifre):
                cevap = QMessageBox.question(self, "Emin misiniz?", "Tüm verileriniz kalıcı olarak silinecek. Onaylıyor musunuz?", QMessageBox.Yes | QMessageBox.No)
                if cevap == QMessageBox.Yes:
                    self.db.kullanici_sil(self.user_id)
                    QMessageBox.information(self, "Başarılı", "Hesabınız başarıyla silindi.")
                    self.cikis_yap()
            else:
                QMessageBox.warning(self, "Hata", "Hatalı şifre girdiniz.")

    def kadro_goster(self, film_dict):
        widget = FilmKadroPenceresi(self, film_dict)
        self.ana_stacked.addWidget(widget)
        self.ana_stacked.setCurrentWidget(widget)

    def kadro_kapat(self, widget):
        self.ana_stacked.setCurrentWidget(self.sekmeler)
        self.ana_stacked.removeWidget(widget)
        widget.deleteLater()

    def degerlendirme_ac(self, movie_id, title, poster_path=None):
        widget = DegerlendirmePenceresi(self, movie_id, title, poster_path)
        self.ana_stacked.addWidget(widget)
        self.ana_stacked.setCurrentWidget(widget)

    def film_detay_goster(self, title, rating, review):
        widget = FilmDetayPenceresi(self, title, rating, review)
        self.ana_stacked.addWidget(widget)
        self.ana_stacked.setCurrentWidget(widget)

    def get_status_color(self, status):
        if status == "İzlendi": return "#2ecc71"
        elif status == "İzlenecek": return "#3498db"
        else: return "#f1c40f"

    def get_stars_text(self, rating):
        if not rating: return "Puanlanmadı"
        r = float(rating)
        full = int(r)
        half = 1 if r - full >= 0.5 else 0
        empty = 5 - full - half
        return ("★" * full) + ("½" * half) + ("☆" * empty)

    def _liste_karti_olustur(self, tmdb_id, title, poster_path, status, rating, review, list_type):
        """İzlediklerim ve Daha Sonra İzle için ortak kart oluşturma."""
        film_kutusu = QWidget()
        width = 180
        height = 310
        film_kutusu.setFixedSize(width, height)
        film_kutusu.setObjectName("ListemKarti")
        
        kutu_layout = QVBoxLayout(film_kutusu)
        kutu_layout.setContentsMargins(8, 8, 8, 8)
        
        poster_container = QWidget()
        afis_width = 160
        afis_height = 240
        poster_container.setFixedSize(afis_width, afis_height)
        
        p_layout = QVBoxLayout(poster_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        
        afis_label = QLabel()
        afis_label.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(afis_label)
        
        overlay = ListHoverOverlayWidget(poster_container, tmdb_id, title, self, list_type)
        overlay.setFixedSize(afis_width, afis_height)
        
        def enter_event(e): overlay.show()
        def leave_event(e): overlay.hide()
        poster_container.enterEvent = enter_event
        poster_container.leaveEvent = leave_event
        
        if poster_path:
            afis_label.setText("Yükleniyor...")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            loader = PosterLoader(self.api, poster_path, self)
            self.active_threads.append(loader)
            loader.poster_downloaded.connect(lambda veri, lbl=afis_label: self.afis_yukle(lbl, veri, afis_width, afis_height))
            loader.finished.connect(lambda t=loader: self.cleanup_thread(t))
            loader.start()
        else:
            afis_label.setText("Afiş Yok")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        
        display_title = title
        if len(display_title) > 18:
            display_title = display_title[:16] + "..."
        
        bilgi_label = QLabel(display_title)
        bilgi_label.setAlignment(Qt.AlignCenter)
        bilgi_label.setStyleSheet("font-size: 13px; font-weight: bold; margin-top: 4px; background: transparent;")
        
        kutu_layout.addWidget(poster_container)
        kutu_layout.addStretch()
        kutu_layout.addWidget(bilgi_label)
        
        # Puan gösterimi (varsa)
        if rating:
            puan_label = QLabel(self.get_stars_text(rating))
            puan_label.setAlignment(Qt.AlignCenter)
            puan_label.setStyleSheet("color: #f5c518; font-size: 18px; background: transparent;")
            kutu_layout.addWidget(puan_label)
        
        # Karta tıklanınca detay penceresi aç
        film_kutusu.setCursor(QCursor(Qt.PointingHandCursor))
        film_kutusu.mousePressEvent = lambda e, t=title, r=rating, rv=review: self.film_detay_goster(t, r, rv)
        
        return film_kutusu

    def izlediklerimi_guncelle(self):
        self.gridi_temizle(self.izlediklerim_grid)
        
        filmler = self.db.kullanicinin_filmlerini_getir(self.user_id)
        izlenenler = [f for f in filmler if f[3] == "İzlendi"]
        
        if not izlenenler:
            bos = QLabel("Henüz izlediğiniz bir içerik yok.")
            bos.setStyleSheet("font-size: 14px; color: #888; background: transparent;")
            self.izlediklerim_grid.addWidget(bos, 0, 0)
            return
        
        satir, sutun = 0, 0
        max_sutun = 4
        for film in izlenenler:
            tmdb_id, title, poster_path, status, rating, review = film
            kutu = self._liste_karti_olustur(tmdb_id, title, poster_path, status, rating, review, 'izlediklerim')
            self.izlediklerim_grid.addWidget(kutu, satir, sutun)
            sutun += 1
            if sutun >= max_sutun:
                sutun = 0
                satir += 1

    def daha_sonra_izle_guncelle(self):
        self.gridi_temizle(self.daha_sonra_grid)
        
        filmler = self.db.kullanicinin_filmlerini_getir(self.user_id)
        izlenecekler = [f for f in filmler if f[3] != "İzlendi"]
        
        if not izlenecekler:
            bos = QLabel("Daha sonra izle listeniz boş.")
            bos.setStyleSheet("font-size: 14px; color: #888; background: transparent;")
            self.daha_sonra_grid.addWidget(bos, 0, 0)
            return
        
        satir, sutun = 0, 0
        max_sutun = 4
        for film in izlenecekler:
            tmdb_id, title, poster_path, status, rating, review = film
            kutu = self._liste_karti_olustur(tmdb_id, title, poster_path, status, rating, review, 'daha_sonra_izle')
            self.daha_sonra_grid.addWidget(kutu, satir, sutun)
            sutun += 1
            if sutun >= max_sutun:
                sutun = 0
                satir += 1

    def listeden_kaldir(self, movie_id, title, list_type):
        cevap = QMessageBox.question(
            self, "Kaldır", 
            f"\"{title}\" listeden kaldırılsın mı?",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap == QMessageBox.Yes:
            self.db.kullanici_film_sil(self.user_id, movie_id)
            if list_type == 'izlediklerim':
                self.izlediklerimi_guncelle()
            else:
                self.daha_sonra_izle_guncelle()

    def sekme_degisti(self, index):
        if index == 1:  # İzlediklerim
            self.izlediklerimi_guncelle()
        elif index == 2:  # Daha Sonra İzle
            self.daha_sonra_izle_guncelle()

    def gridi_temizle(self, grid):
        for i in reversed(range(grid.count())): 
            w = grid.itemAt(i).widget()
            if w:
                grid.removeWidget(w)
                w.setParent(None)

    def arama_geri_don(self):
        self.arama_kutusu.clear()
        self.arama_container.hide()
        self.normal_icerik_container.show()
        
    def arama_yap(self):
        aranan = self.arama_kutusu.text()
        if not aranan: return
        
        self.normal_icerik_container.hide()
        self.arama_container.show()
        
        self.gridi_temizle(self.arama_grid)
        QApplication.processEvents()
        
        lbl = QLabel("Aranıyor...")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        self.arama_grid.addWidget(lbl, 0, 0)
        
        self.arama_butonu.setEnabled(False)
        self.search_loader = SearchLoader(self.api, aranan, self)
        self.active_threads.append(self.search_loader)
        self.search_loader.search_completed.connect(self.arama_sonuclarini_goster)
        self.search_loader.finished.connect(lambda t=self.search_loader: self.cleanup_thread(t))
        self.search_loader.start()

    def arama_sonuclarini_goster(self, sonuclar):
        self.arama_butonu.setEnabled(True)
        self.gridi_temizle(self.arama_grid)
        
        if sonuclar:
            satir, sutun = 0, 0
            for film in sonuclar:
                kutu = self.film_karti_olustur(film)
                self.arama_grid.addWidget(kutu, satir, sutun)
                sutun += 1
                if sutun >= max(1, self.width() // 200):
                    sutun = 0; satir += 1
        else:
            self.arama_grid.addWidget(QLabel("Sonuç bulunamadı."), 0, 0)

    def listeye_ekle(self, film):
        title = film.get('title') or film.get('name', 'Bilinmiyor')
        self.db.film_kaydet(film.get('id'), title, film.get('poster_path', ''))
        return self.db.kullanici_film_ekle(self.user_id, film.get('id'))

    def film_listede_mi(self, movie_id):
        self.db.cursor.execute("SELECT id FROM user_movies WHERE user_id = ? AND movie_id = ?", (self.user_id, movie_id))
        return self.db.cursor.fetchone() is not None

    def temayi_guncelle(self, tema_adi):
        self.secili_tema = tema_adi
        
        # Tema Renk Paletleri
        if tema_adi == "Netflix":
            bg_main = "#0a0a0f"
            bg_gradient = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a24, stop:0.5 #0f0f17, stop:1 #050508)"
            bg_panel = "#1a1a24"
            bg_hover = "#232330"
            text_main = "#FFFFFF"
            text_sec = "#888888"
            accent = "#e50914"
            accent_hover = "#f40612"
            header_bg = "rgba(10, 10, 15, 0.6)"
            tab_selected_bg = "rgba(255, 255, 255, 0.05)"
        elif tema_adi == "IMDb":
            bg_main = "#121212"
            bg_gradient = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #252525, stop:0.5 #121212, stop:1 #000000)"
            bg_panel = "#1f1f1f"
            bg_hover = "#2c2c2c"
            text_main = "#FFFFFF"
            text_sec = "#aaaaaa"
            accent = "#f5c518"
            accent_hover = "#e6b610"
            header_bg = "rgba(0, 0, 0, 0.6)"
            tab_selected_bg = "rgba(255, 255, 255, 0.05)"
        else: # Açık Tema
            bg_main = "#f4f6f8"
            bg_gradient = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.5 #f4f6f8, stop:1 #e0e5ec)"
            bg_panel = "#ffffff"
            bg_hover = "#f0f0f0"
            text_main = "#222222"
            text_sec = "#666666"
            accent = "#3498db"
            accent_hover = "#2980b9"
            header_bg = "rgba(255, 255, 255, 0.6)"
            tab_selected_bg = "rgba(0, 0, 0, 0.05)"

        # Accent metin rengi
        accent_text = "#000000" if tema_adi == "IMDb" else "#FFFFFF"

        # Tab ve Buton ikonlarını tema rengine göre güncelle
        self.sekmeler.setTabIcon(0, qta.icon('fa5s.home', color=text_main))
        self.sekmeler.setTabIcon(1, qta.icon('fa5s.check-circle', color=text_main))
        self.sekmeler.setTabIcon(2, qta.icon('fa5s.clock', color=text_main))
        self.sekmeler.setTabIcon(3, qta.icon('fa5s.cog', color=text_main))
        
        self.arama_butonu.setIcon(qta.icon('fa5s.search', color=accent_text))
        self.arama_geri_btn.setIcon(qta.icon('fa5s.arrow-left', color=accent_text))
        if hasattr(self, 'carousel'):
            self.carousel.btn_prev.setIcon(qta.icon('fa5s.chevron-left', color=accent_text))
            self.carousel.btn_next.setIcon(qta.icon('fa5s.chevron-right', color=accent_text))

        if hasattr(self, 'title_bar'):
            self.title_bar.icon_label.setPixmap(qta.icon('fa5s.film', color=accent).pixmap(16, 16))

        stil = f"""
        QMainWindow, QDialog, QWidget {{ 
            background-color: {bg_main}; 
            color: {text_main}; 
            font-family: 'Segoe UI', Arial; 
        }}
        #MovieAppMerkez {{
            background: {bg_gradient};
        }}
        QMenu, QComboBox QAbstractItemView, QScrollBar {{
            background-color: {bg_panel};
            color: {text_main};
        }}
        QStackedWidget, QStackedWidget > QWidget, QTabWidget::pane, QScrollArea, QScrollArea > QWidget > QWidget, #AnaMenuIcerik, #IcerikPaneli, #YatayIcerik {{
            background-color: transparent;
        }}
        #Header {{
            background-color: {header_bg};
            border-bottom: 2px solid {accent};
        }}
        #HeaderLogo {{ color: {accent}; background: transparent; }}
        #HeaderUser {{ color: {text_main}; background: transparent; }}
        #KategoriBaslik {{
            font-size: 24px;
            font-weight: bold;
            color: {text_main};
            margin-top: 10px;
            background: transparent;
        }}
        QLabel {{ background: transparent; }}
        QLineEdit, QComboBox, QTextEdit {{ 
            background-color: {bg_panel}; 
            border: 1px solid {text_sec}; 
            border-radius: 8px; 
            padding: 8px 15px; 
            color: {text_main}; 
            font-size: 14px;
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
        QComboBox::drop-down {{ border: none; }}
        #PrimaryButon, #EkleButonu {{ 
            background-color: {accent}; 
            color: {accent_text}; 
            border: none; 
            border-radius: 8px; 
            font-weight: bold; 
        }}
        #PrimaryButon:hover, #EkleButonu:hover {{ background-color: {accent_hover}; }}
        
        QTabWidget::pane {{ border: none; background: transparent; }}
        QTabBar::tab {{ 
            background: transparent; 
            color: {text_sec}; 
            padding: 12px 25px; 
            font-size: 16px; 
            font-weight: bold; 
            border: none;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        QTabBar::tab:selected {{ 
            color: {text_main}; 
            border-bottom: 4px solid {accent}; 
            background-color: {tab_selected_bg};
        }}
        QTabBar::tab:hover {{ color: {text_main}; background-color: {tab_selected_bg}; }}
        
        #FilmKarti, #ListemKarti {{
            background-color: {bg_panel};
            border-radius: 12px;
            border: 1px solid rgba(0,0,0,0.1);
        }}
        #FilmKarti:hover, #ListemKarti:hover {{
            background-color: {bg_hover};
            border: 1px solid {accent};
        }}
        #DegerlendirButonu {{
            background-color: {bg_panel};
            color: {text_main};
            border: 1px solid {text_sec};
            border-radius: 5px;
        }}
        #DegerlendirButonu:hover {{ border-color: {accent}; color: {accent}; }}
        #KaldirButonu {{
            background-color: rgba(220, 53, 69, 0.15);
            color: #dc3545;
            border: 1px solid rgba(220, 53, 69, 0.4);
            border-radius: 8px;
            font-weight: bold;
        }}
        #KaldirButonu:hover {{
            background-color: #dc3545;
            color: white;
            border: 1px solid #dc3545;
        }}
        
        QGroupBox#AyarlarGrup {{
            font-size: 18px;
            font-weight: bold;
            color: {text_main};
            border: 1px solid {text_sec};
            border-radius: 10px;
            margin-top: 20px;
            padding-top: 20px;
            background-color: {tab_selected_bg};
        }}
        QGroupBox#AyarlarGrup::title {{ subcontrol-origin: margin; left: 20px; color: {text_main}; }}
        
        QScrollBar:vertical {{
            border: none; background: transparent; width: 10px; margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {text_sec}; min-height: 20px; border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {accent}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
        QScrollBar:horizontal {{
            border: none; background: transparent; height: 10px; margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {text_sec}; min-width: 20px; border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ border: none; background: none; }}

        #CustomTitleBar {{
            background-color: {header_bg};
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }}
        #TitleBarIcon, #TitleBarText {{
            background: transparent;
        }}
        #TitleBarText {{
            font-size: 13px;
            font-weight: 600;
            color: {text_sec};
        }}
        #TitleBtn {{
            background: transparent;
            border: none;
            border-radius: 0px;
            color: {text_sec};
            font-size: 14px;
            font-weight: normal;
        }}
        #TitleBtn:hover {{
            background-color: rgba(255, 255, 255, 0.1);
            color: {text_main};
        }}
        #TitleCloseBtn {{
            background: transparent;
            border: none;
            border-radius: 0px;
            color: {text_sec};
            font-size: 14px;
            font-weight: normal;
        }}
        #TitleCloseBtn:hover {{
            background-color: #e81123;
            color: white;
        }}
        #CustomDialog {{
            border: 1px solid rgba(255, 255, 255, 0.15);
            background-color: {bg_main};
        }}
        #DialogContent {{
            background: transparent;
        }}
        """
        self.setStyleSheet(stil)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'resize_frame'):
            self.resize_frame.update_frame()

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange:
            if hasattr(self, 'title_bar'):
                self.title_bar._update_max_btn()
            if hasattr(self, 'resize_frame'):
                self.resize_frame.update_frame()
        super().changeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = LoginWindow() 
    pencere.show()
    sys.exit(app.exec_())
