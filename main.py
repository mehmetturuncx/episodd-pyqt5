from PyQt5 import QtCore
from dotenv import parser
import sys
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QGridLayout, QScrollArea, QMessageBox, QTabWidget,
                             QDialog, QComboBox, QTextEdit, QDesktopWidget, QGroupBox, QFormLayout, QStackedWidget, QFrame, QCheckBox, QAction, QFileDialog)
from PyQt5.QtGui import QPixmap, QFont, QCursor, QPdfWriter, QTextDocument, QPen, QLinearGradient, QFontMetrics
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, QRect, QRectF, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QSettings, QMarginsF, QSizeF
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

class EpisodeRatingsLoader(QThread):
    ratings_loaded = pyqtSignal(dict, bool)
    
    def __init__(self, api, series_id, total_seasons, imdb_id=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.series_id = series_id
        self.total_seasons = total_seasons
        self.imdb_id = imdb_id
        
    def run(self):
        all_ratings = {}
        is_imdb = False
        
        for s in range(1, self.total_seasons + 1):
            season_data = self.api.dizi_sezon_getir(self.series_id, s)
            if season_data and "episodes" in season_data:
                episodes = season_data["episodes"]
                season_ratings = {}
                for ep in episodes:
                    ep_num = ep.get("episode_number")
                    rating = ep.get("vote_average", 0)
                    if ep_num:
                        season_ratings[ep_num] = rating
                all_ratings[s] = season_ratings

        if self.api.omdb_api_key and self.imdb_id:
            for s in range(1, self.total_seasons + 1):
                season_data = self.api.omdb_sezon_getir(self.imdb_id, s)
                if season_data and season_data.get("Response") == "True":
                    is_imdb = True
                    episodes = season_data.get("Episodes", [])
                    if s not in all_ratings:
                        all_ratings[s] = {}
                        
                    for ep in episodes:
                        try:
                            ep_num = int(ep.get("Episode"))
                            rating_str = ep.get("imdbRating", "0")
                            if rating_str != "N/A":
                                rating = float(rating_str)
                                all_ratings[s][ep_num] = rating
                        except ValueError:
                            pass
                    
        self.ratings_loaded.emit(all_ratings, is_imdb)

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
        self.setWindowTitle("episodd")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(600, 500)

        self.settings = QSettings("episodd", "AppConfig")
        self.db = DatabaseManager()
        self.arayuzu_hazirla()
        self.arayuzu_guncelle()
        self.ayarlari_yukle()
        self.temayi_uygula()

        self.resize_frame = ResizeFrame(self)
        self.showMaximized()
        
    def arayuzu_guncelle(self):
        self.kullanici_input.setPlaceholderText("Kullanıcı Adı")
        self.sifre_input.setPlaceholderText("Şifre")
        self.beni_hatirla_cb.setText("Beni Hatırla")
        self.giris_butonu.setText("Giriş Yap")
        self.gecis_lbl.setText("Hesabın yok mu?")
        self.kayda_gec_btn.setText("Kayıt Ol")
        
        self.k_baslik.setText("Kayıt Ol")
        self.k_kullanici_input.setPlaceholderText("Kullanıcı Adı")
        self.k_sifre_input.setPlaceholderText("Şifre")
        self.k_sifre_tekrar.setPlaceholderText("Şifre (Tekrar)")
        self.kayit_butonu.setText("Kayıt Ol")
        self.geri_lbl.setText("Zaten hesabın var mı?")
        self.girise_gec_btn.setText("Giriş Yap")

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
        self.title_bar = CustomTitleBar(self, "episodd")
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
        self.gecis_lbl = QLabel("Hesabın yok mu?")
        self.gecis_lbl.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.kayda_gec_btn = QPushButton("Kayıt Ol")
        self.kayda_gec_btn.setStyleSheet("color: #e50914; background: transparent; font-weight: bold; border: none;")
        self.kayda_gec_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.kayda_gec_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        
        gecis_layout.addStretch()
        gecis_layout.addWidget(self.gecis_lbl)
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

        self.k_baslik = QLabel("Kayıt Ol")
        self.k_baslik.setAlignment(Qt.AlignCenter)
        self.k_baslik.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 40px; color: #ffffff; background: transparent;")
        k_layout.addWidget(self.k_baslik)

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
        self.geri_lbl = QLabel("Zaten hesabın var mı?")
        self.geri_lbl.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.girise_gec_btn = QPushButton("Giriş Yap")
        self.girise_gec_btn.setStyleSheet("color: #e50914; background: transparent; font-weight: bold; border: none;")
        self.girise_gec_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.girise_gec_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        
        geri_layout.addStretch()
        geri_layout.addWidget(self.geri_lbl)
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
    def __init__(self, main_app, movie_id, film_adi, poster_path=None, media_type='movie'):
        super().__init__(main_app)
        self.main_app = main_app
        self.movie_id = movie_id
        self.film_adi = film_adi
        self.poster_path = poster_path
        self.media_type = media_type
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

        existing = self.main_app.db.kullanici_film_detay_getir(self.main_app.user_id, self.movie_id)
        existing_rating = 0
        existing_review = ""
        if existing:
            status, rating, review = existing
            if rating: existing_rating = float(rating)
            if review: existing_review = review

        lbl_puan = QLabel("Puanın (5 Üzerinden):")
        lbl_puan.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        form_v_layout.addWidget(lbl_puan)
        
        self.puan_widget = StarRatingWidget()
        self.puan_widget.setValue(existing_rating if existing_rating > 0 else 2.5)
        form_v_layout.addWidget(self.puan_widget)

        lbl_yorum = QLabel("Yorumun:")
        lbl_yorum.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; margin-top: 15px;")
        form_v_layout.addWidget(lbl_yorum)
        
        self.yorum_kutusu = QTextEdit()
        if existing_review:
            self.yorum_kutusu.setText(existing_review)
        else:
            self.yorum_kutusu.setPlaceholderText("Film hakkında ne düşünüyorsun?")
        form_v_layout.addWidget(self.yorum_kutusu)

        self.kaydet_butonu = QPushButton(" " + "Kaydet")
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
        
        # Veritabanına kaydedilmemişse önce kaydet (ana menüden değerlendirme yapıldıysa)
        self.main_app.db.film_kaydet(self.movie_id, self.film_adi, self.poster_path, self.media_type)
        self.main_app.db.kullanici_film_ekle(self.main_app.user_id, self.movie_id, status)
        
        # Sonra değerlendirmeyi güncelle
        self.main_app.db.film_degerlendir(self.main_app.user_id, self.movie_id, status, rating, review)
        
        current_tab = self.main_app.sekmeler.currentIndex()
        if current_tab == 1:
            self.main_app.izlediklerimi_guncelle()
        elif current_tab == 2:
            self.main_app.daha_sonra_izle_guncelle()
            
        self.main_app.buton_durumlarini_guncelle()
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
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QScrollArea.NoFrame)
        self.main_scroll.setStyleSheet("background: transparent;")
        
        self.content_widget = QWidget()
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(30, 30, 30, 30)
        
        self.main_scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.main_scroll)
        
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
        
        self.degerlendirme_container = QWidget()
        self.degerlendirme_container.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 8px;")
        self.degerlendirme_layout = QVBoxLayout(self.degerlendirme_container)
        self.degerlendirme_layout.setContentsMargins(15, 10, 15, 10)
        self.degerlendirme_layout.setSpacing(5)
        self.degerlendirme_container.hide()
        self.detay_v_layout.addWidget(self.degerlendirme_container)
        
        # Action Buttons
        self.actions_layout = QHBoxLayout()
        
        self.btn_daha_sonra = QPushButton(" " + " Daha Sonra İzle")
        self.btn_daha_sonra.setIcon(qta.icon('fa5s.clock', color='white'))
        self.btn_daha_sonra.setObjectName("SecondaryButon")
        self.btn_daha_sonra.setFixedSize(160, 40)
        self.btn_daha_sonra.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_daha_sonra.clicked.connect(self.daha_sonra_izle_ekle)
        self.actions_layout.addWidget(self.btn_daha_sonra)
        
        self.btn_degerlendir = QPushButton(" " + " Değerlendir")
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

        self.durum_guncelle()
            
        # Ayırıcı
        ayirici = QWidget()
        ayirici.setFixedHeight(2)
        ayirici.setStyleSheet("background-color: rgba(255,255,255,0.1); margin: 20px 0;")
        self.layout.addWidget(ayirici)
        
        # Alt Kısım: Oyuncular
        self.oyuncu_layout = QHBoxLayout()
        self.oyuncu_layout.setAlignment(Qt.AlignLeft)
        self.oyuncu_layout.setSpacing(25)
        
        self.oyuncu_container = QWidget()
        self.oyuncu_container.setLayout(self.oyuncu_layout)
        self.oyuncu_container.setStyleSheet("background-color: transparent;")
        
        self.layout.addWidget(self.oyuncu_container)
        
        self.heatmap_container = QWidget()
        self.heatmap_layout = QVBoxLayout(self.heatmap_container)
        self.heatmap_layout.setContentsMargins(0, 20, 0, 0)
        self.heatmap_layout.setSpacing(10)
        
        self.heatmap_baslik = QLabel("Bölüm Puanları (Yükleniyor...)")
        self.heatmap_baslik.setStyleSheet("font-size: 20px; font-weight: bold; color: #f5c518; background: transparent;")
        self.heatmap_layout.addWidget(self.heatmap_baslik)
        
        self.heatmap_grid_container = QWidget()
        self.heatmap_grid_layout = QGridLayout(self.heatmap_grid_container)
        self.heatmap_grid_layout.setSpacing(3)
        self.heatmap_grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.heatmap_layout.addWidget(self.heatmap_grid_container)
        
        self.heatmap_container.hide()
        self.layout.addWidget(self.heatmap_container)
        
    def durum_guncelle(self):
        if self.film:
            if self.main_app.film_listede_mi(self.film.get('id')):
                self.btn_daha_sonra.setText("  Eklendi")
                self.btn_daha_sonra.setStyleSheet("background-color: #2ecc71; color: white;")
                self.btn_daha_sonra.setEnabled(False)
            else:
                self.btn_daha_sonra.setText("  Daha Sonra İzle")
                self.btn_daha_sonra.setStyleSheet("")
                self.btn_daha_sonra.setEnabled(True)
                
            existing = self.main_app.db.kullanici_film_detay_getir(self.main_app.user_id, self.film.get('id'))
            if existing and existing[1]: 
                status, rating, review = existing
                
                for i in reversed(range(self.degerlendirme_layout.count())): 
                    w = self.degerlendirme_layout.itemAt(i).widget()
                    if w:
                        self.degerlendirme_layout.removeWidget(w)
                        w.setParent(None)
                        
                baslik = QLabel("Değerlendirmen")
                baslik.setStyleSheet("font-size: 16px; font-weight: bold; color: #f5c518; background: transparent;")
                self.degerlendirme_layout.addWidget(baslik)
                
                puan_w = StarRatingWidget()
                puan_w.setValue(float(rating))
                puan_w.setEnabled(False) 
                self.degerlendirme_layout.addWidget(puan_w)
                
                if review:
                    yorum_lbl = QLabel(review)
                    yorum_lbl.setWordWrap(True)
                    yorum_lbl.setStyleSheet("font-size: 14px; color: #ddd; background: transparent; font-style: italic;")
                    self.degerlendirme_layout.addWidget(yorum_lbl)
                    
                self.degerlendirme_container.show()
            else:
                self.degerlendirme_container.hide()
        
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
        try:
            pixmap = QPixmap()
            if pixmap.loadFromData(veri):
                self.poster_lbl.setPixmap(pixmap.scaled(250, 375, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.poster_lbl.setText("")
        except RuntimeError:
            pass
        
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
            actor_widget.setFixedSize(120, 180)
            vbox = QVBoxLayout(actor_widget)
            vbox.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
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
            
        media_type = self.film.get('media_type', 'movie')
        if media_type == 'tv':
            total_seasons = details.get("number_of_seasons", 0)
            if total_seasons > 0:
                self.heatmap_container.show()
                imdb_id = details.get("external_ids", {}).get("imdb_id")
                self.heatmap_loader = EpisodeRatingsLoader(self.main_app.api, self.film.get('id'), total_seasons, imdb_id, self)
                self.active_loaders.append(self.heatmap_loader)
                self.heatmap_loader.ratings_loaded.connect(self.heatmap_ciz)
                self.heatmap_loader.finished.connect(lambda t=self.heatmap_loader: self.cleanup_thread(t))
                self.heatmap_loader.start()
                
    def heatmap_ciz(self, all_ratings, is_imdb=False):
        kaynak = "IMDB" if is_imdb else "TMDB"
        self.heatmap_baslik.setText(f"Bölüm Puanları ({kaynak})")
        
        def get_color(rating):
            if rating == 0: return "#333333"
            elif rating >= 9.7: return "#1DA1F2"
            elif rating >= 9.0: return "#186A3B"
            elif rating >= 8.0: return "#25A95D"
            elif rating >= 7.0: return "#F4D03F"
            elif rating >= 6.0: return "#F39C12"
            elif rating >= 5.0: return "#E74C3C"
            else: return "#633974"
            
        max_episodes = 0
        for s, eps in all_ratings.items():
            if eps:
                max_episodes = max(max_episodes, max(eps.keys()))
                
        for ep_num in range(1, max_episodes + 1):
            bolum_lbl = QLabel(f"E{ep_num}")
            bolum_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bolum_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #888; background: transparent; padding-right: 8px;")
            bolum_lbl.setFixedSize(35, 35)
            self.heatmap_grid_layout.addWidget(bolum_lbl, ep_num, 0)
            
        for col_idx, s in enumerate(sorted(all_ratings.keys()), start=1):
            sezon_lbl = QLabel(f"S{s}")
            sezon_lbl.setAlignment(Qt.AlignCenter)
            sezon_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaa; background: transparent; padding-bottom: 5px;")
            sezon_lbl.setFixedSize(55, 30)
            self.heatmap_grid_layout.addWidget(sezon_lbl, 0, col_idx)
            
            eps = all_ratings[s]
            for ep_num in range(1, max_episodes + 1):
                box = QLabel()
                box.setFixedSize(55, 35)
                box.setAlignment(Qt.AlignCenter)
                
                if ep_num in eps:
                    rating = eps[ep_num]
                    rounded_rating = round(rating, 1)
                    color = get_color(rounded_rating)
                    box.setStyleSheet(f"background-color: {color}; color: {'#fff' if rounded_rating >= 8.0 else '#111'}; font-weight: bold; border-radius: 4px; font-size: 14px;")
                    if rating > 0:
                        box.setText(f"{rounded_rating:.1f}")
                    else:
                        box.setText("-")
                else:
                    box.setStyleSheet("background-color: transparent;")
                    
                self.heatmap_grid_layout.addWidget(box, ep_num, col_idx)
            
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
        eklendi_mi = self.main_app.listeye_ekle(self.film)
        if eklendi_mi:
            self.main_app.daha_sonra_izle_guncelle()
        
        self.btn_daha_sonra.setText("  Eklendi")
        self.btn_daha_sonra.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_daha_sonra.setEnabled(False)

    def degerlendirme_sayfasi_ac(self):
        film_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        poster_path = self.film.get('poster_path')
        media_type = self.film.get('media_type', 'movie')
        self.main_app.degerlendirme_ac(film_id, title, poster_path, media_type)

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
        
        self.btn_izle = QPushButton(" " + " Daha Sonra İzle")
        self.btn_izle.setIcon(qta.icon('fa5s.clock', color='white'))
        self.btn_izle.setObjectName("PrimaryButon")
        self.btn_izle.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_izle.setFixedHeight(35)
        self.btn_izle.clicked.connect(self.daha_sonra_izle)
        
        self.btn_degerlendir = QPushButton(" " + " Değerlendir")
        self.btn_degerlendir.setIcon(qta.icon('fa5s.star', color='white'))
        self.btn_degerlendir.setObjectName("PrimaryButon")
        self.btn_degerlendir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_degerlendir.setFixedHeight(35)
        self.btn_degerlendir.clicked.connect(self.degerlendir)
        
        layout.addWidget(self.btn_izle)
        layout.addWidget(self.btn_degerlendir)
        self.hide()
        
        if self.film and self.main_app.film_listede_mi(self.film.get('id')):
            self.btn_izle.setText("  Eklendi")
            self.btn_izle.setStyleSheet("background-color: #2ecc71; color: white;")
            self.btn_izle.setEnabled(False)
            
    def durum_guncelle(self):
        if self.film:
            if self.main_app.film_listede_mi(self.film.get('id')):
                self.btn_izle.setText("  Eklendi")
                self.btn_izle.setStyleSheet("background-color: #2ecc71; color: white;")
                self.btn_izle.setEnabled(False)
            else:
                self.btn_izle.setText("  Daha Sonra İzle")
                self.btn_izle.setStyleSheet("")
                self.btn_izle.setEnabled(True)
        
    def daha_sonra_izle(self):
        eklendi_mi = self.main_app.listeye_ekle(self.film)
        if eklendi_mi:
            self.main_app.daha_sonra_izle_guncelle()
            
        self.btn_izle.setText("  Eklendi")
        self.btn_izle.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_izle.setEnabled(False)
        
    def degerlendir(self):
        movie_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        poster_path = self.film.get('poster_path')
        media_type = self.film.get('media_type', 'movie')
        self.main_app.degerlendirme_ac(movie_id, title, poster_path, media_type)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.main_app.kadro_goster(self.film)


class ListHoverOverlayWidget(QWidget):
    """Hover overlay for list items (İzlediklerim / Daha Sonra İzle) with Değerlendir and Kaldır buttons."""
    def __init__(self, parent=None, tmdb_id=None, title=None, main_app=None, list_type=None, media_type='movie', poster_path=None):
        super().__init__(parent)
        self.tmdb_id = tmdb_id
        self.title = title
        self.main_app = main_app
        self.list_type = list_type  # 'izlediklerim' or 'daha_sonra_izle'
        self.media_type = media_type
        self.poster_path = poster_path
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7); border-radius: 8px;")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.btn_degerlendir = QPushButton(" " + " Değerlendir")
        self.btn_degerlendir.setIcon(qta.icon('fa5s.star', color='white'))
        self.btn_degerlendir.setObjectName("PrimaryButon")
        self.btn_degerlendir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_degerlendir.setFixedHeight(35)
        self.btn_degerlendir.clicked.connect(self.degerlendir)
        
        self.btn_kaldir = QPushButton(" " + " Kaldır")
        self.btn_kaldir.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        self.btn_kaldir.setObjectName("KaldirButonu")
        self.btn_kaldir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_kaldir.setFixedHeight(35)
        self.btn_kaldir.clicked.connect(self.kaldir)
        
        layout.addWidget(self.btn_degerlendir)
        layout.addWidget(self.btn_kaldir)
        self.hide()
    
    def degerlendir(self):
        self.main_app.degerlendirme_ac(self.tmdb_id, self.title, getattr(self, 'poster_path', None), getattr(self, 'media_type', 'movie'))
    
    def kaldir(self):
        self.main_app.listeden_kaldir(self.tmdb_id, self.title, self.list_type)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            film_dict = {
                'id': self.tmdb_id, 
                'title': self.title, 
                'media_type': getattr(self, 'media_type', 'movie'),
                'poster_path': getattr(self, 'poster_path', None)
            }
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
        
    def arayuzu_guncelle(self):
        self.sekmeler.setTabText(0, " " + "Ana Sayfa")
        self.sekmeler.setTabText(1, " " + " İzlediklerim")
        self.sekmeler.setTabText(2, " " + " Daha Sonra İzle")
        self.sekmeler.setTabText(3, " " + " Ayarlar")
        
        self.arama_kutusu.setPlaceholderText("Film veya dizi ara...")
        self.arama_butonu.setText("  Ara")
        self.arama_baslik.setText("  Arama Sonuçları")
        self.arama_geri_btn.setText("  Geri Dön")
        
        self.baslik_yeni_cikanlar.setText("  Yeni Çıkanlar")
        self.baslik_top_filmler.setText("  En Yüksek Puanlı Filmler")
        self.baslik_top_diziler.setText("  Popüler Diziler")
        
        self.izlediklerim_baslik.setText("  İzlediklerim")
        self.daha_sonra_baslik.setText("  Daha Sonra İzle")
        
        self.ayarlar_ana_baslik.setText(" Ayarlar")
        self.kullanici_grup.setTitle("Profil Bilgileri")
        self.kullanici_bilgi_lbl.setText(f"Mevcut Kullanıcı Adı: {self.username}")
        self.k_degistir_btn.setText(" Kullanıcı Adı Değiştir")
        self.s_degistir_btn.setText(" Şifre Değiştir")
        self.gorunum_grup.setTitle("Uygulama Ayarları")
        self.t_lbl.setText("Uygulama Teması:")
        self.tehlikeli_grup.setTitle("Tehlikeli Bölge")
        self.uyari_lbl.setText("Dikkat: Hesabınızı silmek tüm izleme geçmişinizi, puanlarınızı ve değerlendirmelerinizi kalıcı olarak siler. Bu işlem geri alınamaz.")
        self.sil_btn.setText("  Hesabı Kalıcı Olarak Sil")
        if hasattr(self, 'kullanici_hosgeldin'):
            self.kullanici_hosgeldin.setText(f"Hoşgeldin, {self.username}")

    

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
        try:
            pixmap = QPixmap()
            if pixmap.loadFromData(veri):
                label.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                label.setText("")
        except RuntimeError:
            pass

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
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.arama_yap)
        
        self.arama_kutusu.textChanged.connect(self.arama_metni_degisti)
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
        
        self.baslik_yeni_cikanlar = QLabel(" Yeni Çıkanlar")
        self.baslik_yeni_cikanlar.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(self.baslik_yeni_cikanlar)
        
        self.carousel = CarouselWidget(self.api, self)
        self.normal_icerik_layout.addWidget(self.carousel)
        
        self.baslik_top_filmler = QLabel(" En Yüksek Puanlı Filmler")
        self.baslik_top_filmler.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(self.baslik_top_filmler)
        
        top_scroll = QScrollArea()
        top_scroll.setFixedHeight(340)
        top_scroll.setWidgetResizable(True)
        top_icerik = QWidget()
        top_icerik.setObjectName("YatayIcerik")
        self.top_layout = QHBoxLayout(top_icerik)
        self.top_layout.setAlignment(Qt.AlignLeft)
        top_scroll.setWidget(top_icerik)
        self.normal_icerik_layout.addWidget(top_scroll)

        self.baslik_top_diziler = QLabel(" Popüler Diziler")
        self.baslik_top_diziler.setObjectName("KategoriBaslik")
        self.normal_icerik_layout.addWidget(self.baslik_top_diziler)

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

        self.top_layout.addWidget(QLabel("Yükleniyor..."))
        self.top_dizi_layout.addWidget(QLabel("Yükleniyor..."))

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
        
        self.izlediklerim_baslik = QLabel(" İzlediklerim")
        self.izlediklerim_baslik.setObjectName("KategoriBaslik")
        layout.addWidget(self.izlediklerim_baslik)

        self.izlediklerim_scroll = QScrollArea()
        self.izlediklerim_scroll.setWidgetResizable(True)
        self.izlediklerim_icerik = QWidget()
        self.izlediklerim_icerik.setObjectName("IcerikPaneli")
        self.izlediklerim_grid = QHBoxLayout(self.izlediklerim_icerik)
        self.izlediklerim_grid.setSpacing(20)
        self.izlediklerim_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.izlediklerim_scroll.setWidget(self.izlediklerim_icerik)
        
        layout.addWidget(self.izlediklerim_scroll)

    def daha_sonra_sekmesini_kur(self):
        layout = QVBoxLayout(self.daha_sonra_sekmesi)
        layout.setContentsMargins(20, 20, 20, 20)
        
        baslik_layout = QHBoxLayout()
        self.daha_sonra_baslik = QLabel(" Daha Sonra İzle")
        self.daha_sonra_baslik.setObjectName("KategoriBaslik")
        
        self.btn_pdf_disa_aktar = QPushButton(" PDF Olarak Dışa Aktar")
        self.btn_pdf_disa_aktar.setIcon(qta.icon('fa5s.file-pdf', color='white'))
        self.btn_pdf_disa_aktar.setObjectName("PrimaryButon")
        self.btn_pdf_disa_aktar.setFixedSize(220, 35)
        self.btn_pdf_disa_aktar.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_pdf_disa_aktar.clicked.connect(self.daha_sonra_pdf_aktar)
        
        baslik_layout.addWidget(self.daha_sonra_baslik)
        baslik_layout.addStretch()
        baslik_layout.addWidget(self.btn_pdf_disa_aktar)
        
        layout.addLayout(baslik_layout)

        self.daha_sonra_scroll = QScrollArea()
        self.daha_sonra_scroll.setWidgetResizable(True)
        self.daha_sonra_icerik = QWidget()
        self.daha_sonra_icerik.setObjectName("IcerikPaneli")
        self.daha_sonra_grid = QHBoxLayout(self.daha_sonra_icerik)
        self.daha_sonra_grid.setSpacing(20)
        self.daha_sonra_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.daha_sonra_scroll.setWidget(self.daha_sonra_icerik)
        
        layout.addWidget(self.daha_sonra_scroll)

    def daha_sonra_pdf_aktar(self):
        filmler = self.db.kullanicinin_filmlerini_getir(self.user_id)
        izlenecekler = [f for f in filmler if f[3] == 'izlenecek']
        
        if not izlenecekler:
            QMessageBox.warning(self, "Uyarı", "Daha Sonra İzle listeniz boş.")
            return
            
        dosya_yolu, _ = QFileDialog.getSaveFileName(self, "PDF Olarak Kaydet", "", "PDF Dosyaları (*.pdf)")
        if not dosya_yolu:
            return
            
        if not dosya_yolu.endswith('.pdf'):
            dosya_yolu += '.pdf'
            
        try:
            from PyQt5.QtGui import QPageSize, QPageLayout
            from PyQt5.QtCore import QDate
            
            pdf = QPdfWriter(dosya_yolu)
            pdf.setPageSize(QPageSize(QPageSize.A4))
            pdf.setPageMargins(QMarginsF(0, 0, 0, 0))
            res = pdf.resolution()
            
            page_w = int(8.27 * res)
            page_h = int(11.69 * res)
            margin = int(0.6 * res)
            content_w = page_w - 2 * margin
            
            # Card dimensions
            card_h = int(1.1 * res)
            card_gap = int(0.15 * res)
            poster_w = int(0.6 * res)
            poster_h = int(0.9 * res)
            
            header_h = int(1.6 * res)
            footer_h = int(0.4 * res)
            
            # Pre-download poster images
            poster_cache = {}
            for film in izlenecekler:
                poster_path = film[2]
                if poster_path:
                    veri = self.api.poster_indir(poster_path)
                    if veri:
                        pix = QPixmap()
                        if pix.loadFromData(veri):
                            poster_cache[film[0]] = pix
            
            painter = QPainter(pdf)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            
            page_num = 1
            total_pages = 1
            usable_h = page_h - header_h - footer_h - margin
            items_per_page_first = int(usable_h / (card_h + card_gap))
            usable_h_rest = page_h - margin - footer_h - int(0.3 * res)
            items_per_page_rest = int(usable_h_rest / (card_h + card_gap))
            remaining = len(izlenecekler) - items_per_page_first
            if remaining > 0:
                total_pages += (remaining + items_per_page_rest - 1) // items_per_page_rest

            def draw_page_bg():
                bg_grad = QLinearGradient(0, 0, 0, page_h)
                bg_grad.setColorAt(0, QColor("#0f0f17"))
                bg_grad.setColorAt(0.5, QColor("#141420"))
                bg_grad.setColorAt(1, QColor("#0a0a10"))
                painter.fillRect(0, 0, page_w, page_h, bg_grad)

            def draw_footer(pg, total):
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(QColor("#555555"))
                footer_y = page_h - footer_h
                painter.drawLine(margin, footer_y, page_w - margin, footer_y)
                painter.drawText(QRect(margin, footer_y, content_w, footer_h), Qt.AlignLeft | Qt.AlignVCenter, "episodd")
                painter.drawText(QRect(margin, footer_y, content_w, footer_h), Qt.AlignRight | Qt.AlignVCenter, f"Sayfa {pg} / {total}")

            def draw_header():
                # Header gradient bar
                hdr_grad = QLinearGradient(margin, 0, margin + content_w, 0)
                hdr_grad.setColorAt(0, QColor("#e50914"))
                hdr_grad.setColorAt(1, QColor("#b80710"))
                hdr_rect_path = QPainterPath()
                hdr_rect_path.addRoundedRect(QRectF(margin, margin, content_w, int(0.45 * res)), 10, 10)
                painter.fillPath(hdr_rect_path, hdr_grad)
                
                # Header text
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
                text_rect = QRect(margin + int(0.15 * res), margin, content_w, int(0.45 * res))
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, "🎬  Daha Sonra İzle Listesi")
                
                # Subtitle / date
                subtitle_y = margin + int(0.55 * res)
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#888888"))
                today = QDate.currentDate().toString("dd.MM.yyyy")
                painter.drawText(QRect(margin, subtitle_y, content_w, int(0.2 * res)), Qt.AlignLeft | Qt.AlignVCenter,
                                 f"{self.username} • {len(izlenecekler)} yapım • {today}")
                
                # Thin separator line
                sep_y = margin + int(0.85 * res)
                painter.setPen(QPen(QColor("#2a2a3a"), 1))
                painter.drawLine(margin, sep_y, page_w - margin, sep_y)

            def draw_card(x, y, idx, film):
                tmdb_id = film[0]
                title = film[1]
                media_type_str = film[6]
                
                # Card background
                card_bg = QPainterPath()
                card_bg.addRoundedRect(QRectF(x, y, content_w, card_h), 8, 8)
                painter.fillPath(card_bg, QColor("#1a1a28"))
                
                # Card border
                painter.setPen(QPen(QColor("#2a2a3a"), 1))
                painter.drawPath(card_bg)
                
                pad = int(0.08 * res)
                
                # Poster
                poster_x = x + pad
                poster_y = y + (card_h - poster_h) // 2
                
                if tmdb_id in poster_cache:
                    pix = poster_cache[tmdb_id].scaled(poster_w, poster_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    poster_path = QPainterPath()
                    poster_path.addRoundedRect(QRectF(poster_x, poster_y, poster_w, poster_h), 5, 5)
                    painter.save()
                    painter.setClipPath(poster_path)
                    painter.drawPixmap(poster_x, poster_y, pix)
                    painter.restore()
                else:
                    # Placeholder
                    placeholder_path = QPainterPath()
                    placeholder_path.addRoundedRect(QRectF(poster_x, poster_y, poster_w, poster_h), 5, 5)
                    painter.fillPath(placeholder_path, QColor("#252535"))
                    painter.setFont(QFont("Segoe UI", 7))
                    painter.setPen(QColor("#555555"))
                    painter.drawText(QRect(poster_x, poster_y, poster_w, poster_h), Qt.AlignCenter, "Afiş\nYok")
                
                # Text area
                text_x = poster_x + poster_w + int(0.15 * res)
                text_w = content_w - poster_w - pad * 2 - int(0.15 * res)
                
                # Number badge
                badge_size = int(0.22 * res)
                badge_x = text_x
                badge_y = y + pad
                badge_path = QPainterPath()
                badge_path.addRoundedRect(QRectF(badge_x, badge_y, badge_size, badge_size), 4, 4)
                painter.fillPath(badge_path, QColor("#e50914"))
                painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRect(badge_x, badge_y, badge_size, badge_size), Qt.AlignCenter, str(idx))
                
                # Title
                title_x = badge_x + badge_size + int(0.08 * res)
                title_y = badge_y
                title_w = text_w - badge_size - int(0.08 * res)
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                title_rect = QRect(title_x, title_y, title_w, int(0.3 * res))
                painter.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, title)
                
                # Type badge
                type_label = "DİZİ" if media_type_str == "tv" else "FİLM"
                type_color = QColor("#3b82f6") if media_type_str == "tv" else QColor("#e50914")
                type_badge_w = int(0.45 * res)
                type_badge_h = int(0.18 * res)
                type_x = text_x
                type_y = y + card_h - pad - type_badge_h
                type_path = QPainterPath()
                type_path.addRoundedRect(QRectF(type_x, type_y, type_badge_w, type_badge_h), 4, 4)
                painter.fillPath(type_path, type_color)
                painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRect(type_x, type_y, type_badge_w, type_badge_h), Qt.AlignCenter, type_label)

            # --- Draw pages ---
            draw_page_bg()
            draw_header()
            draw_footer(page_num, total_pages)
            
            cursor_y = header_h
            items_on_page = 0
            max_items_this_page = items_per_page_first
            
            for idx, film in enumerate(izlenecekler, 1):
                if items_on_page >= max_items_this_page:
                    # New page
                    pdf.newPage()
                    page_num += 1
                    draw_page_bg()
                    draw_footer(page_num, total_pages)
                    cursor_y = margin + int(0.3 * res)
                    items_on_page = 0
                    max_items_this_page = items_per_page_rest
                
                draw_card(margin, cursor_y, idx, film)
                cursor_y += card_h + card_gap
                items_on_page += 1
            
            painter.end()
            
            QMessageBox.information(self, "Başarılı", "Liste başarıyla PDF olarak dışa aktarıldı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulurken bir hata oluştu:\n{str(e)}")

    def ayarlar_sekmesini_kur(self):
        layout = QVBoxLayout(self.ayarlar_sekmesi)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignTop)

        # Başlık
        self.ayarlar_ana_baslik = QLabel("Hesap ve Uygulama Ayarları")
        self.ayarlar_ana_baslik.setStyleSheet("font-size: 28px; font-weight: bold; color: white; background: transparent;")
        layout.addWidget(self.ayarlar_ana_baslik)

        # Kullanıcı Bilgileri
        self.kullanici_grup = QGroupBox("Profil Bilgileri")
        self.kullanici_grup.setObjectName("AyarlarGrup")
        k_layout = QVBoxLayout(self.kullanici_grup)
        k_layout.setSpacing(15)

        self.kullanici_bilgi_lbl = QLabel(f"Mevcut Kullanıcı Adı: {self.username}")
        self.kullanici_bilgi_lbl.setStyleSheet("font-size: 16px; color: white; background: transparent;")
        k_layout.addWidget(self.kullanici_bilgi_lbl)

        btn_h = QHBoxLayout()
        self.k_degistir_btn = QPushButton(" Kullanıcı Adı Değiştir")
        self.k_degistir_btn.setIcon(qta.icon('fa5s.user-edit', color='white'))
        self.k_degistir_btn.setObjectName("PrimaryButon")
        self.k_degistir_btn.setFixedSize(220, 40)
        self.k_degistir_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.k_degistir_btn.clicked.connect(self.kullanici_adi_degistir_dialog)
        
        self.s_degistir_btn = QPushButton(" Şifre Değiştir")
        self.s_degistir_btn.setIcon(qta.icon('fa5s.key', color='white'))
        self.s_degistir_btn.setObjectName("PrimaryButon")
        self.s_degistir_btn.setFixedSize(180, 40)
        self.s_degistir_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.s_degistir_btn.clicked.connect(self.sifre_degistir_dialog)
        
        btn_h.addWidget(self.k_degistir_btn)
        btn_h.addWidget(self.s_degistir_btn)
        btn_h.addStretch()
        k_layout.addLayout(btn_h)
        
        layout.addWidget(self.kullanici_grup)

        # Görünüm
        self.gorunum_grup = QGroupBox("Uygulama Ayarları")
        self.gorunum_grup.setObjectName("AyarlarGrup")
        g_layout = QVBoxLayout(self.gorunum_grup)
        
        t_h = QHBoxLayout()
        self.t_lbl = QLabel("Uygulama Teması:")
        self.t_lbl.setStyleSheet("font-size: 16px; color: white; background: transparent;")
        
        self.ayar_tema = QComboBox()
        self.ayar_tema.addItems(["Netflix", "IMDb", "Açık Tema"])
        self.ayar_tema.setCurrentText(self.secili_tema)
        self.ayar_tema.setFixedSize(200, 40)
        self.ayar_tema.currentTextChanged.connect(self.temayi_guncelle)
        
        t_h.addWidget(self.t_lbl)
        t_h.addWidget(self.ayar_tema)
        t_h.addStretch()
        g_layout.addLayout(t_h)
        

        
        layout.addWidget(self.gorunum_grup)
        
        # Tehlikeli Bölge
        self.tehlikeli_grup = QGroupBox("Tehlikeli Bölge")
        self.tehlikeli_grup.setStyleSheet("QGroupBox { border: 1px solid #e50914; border-radius: 8px; margin-top: 10px; } QGroupBox::title { color: #e50914; subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
        t_layout = QVBoxLayout(self.tehlikeli_grup)
        t_layout.setSpacing(10)
        
        self.uyari_lbl = QLabel("Dikkat: Hesabınızı silmek tüm izleme geçmişinizi, puanlarınızı ve değerlendirmelerinizi kalıcı olarak siler. Bu işlem geri alınamaz.")
        self.uyari_lbl.setWordWrap(True)
        self.uyari_lbl.setStyleSheet("color: #aaaaaa; font-size: 14px; background: transparent;")
        t_layout.addWidget(self.uyari_lbl)
        
        self.sil_btn = QPushButton(" Hesabı Kalıcı Olarak Sil")
        self.sil_btn.setIcon(qta.icon('fa5s.exclamation-triangle', color='white'))
        self.sil_btn.setStyleSheet("background-color: #e50914; color: white; border-radius: 8px; font-weight: bold; padding: 0 10px;")
        self.sil_btn.setFixedSize(250, 45)
        self.sil_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.sil_btn.clicked.connect(self.hesap_sil_dialog)
        t_layout.addWidget(self.sil_btn)
        
        layout.addWidget(self.tehlikeli_grup)
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
        if hasattr(widget, 'active_loaders'):
            for t in widget.active_loaders:
                t.setParent(None)
        widget.deleteLater()

    def degerlendirme_ac(self, movie_id, title, poster_path=None, media_type='movie'):
        widget = DegerlendirmePenceresi(self, movie_id, title, poster_path, media_type)
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

    def _liste_karti_olustur(self, tmdb_id, title, poster_path, status, rating, review, list_type, media_type='movie'):
        """İzlediklerim ve Daha Sonra İzle için ortak kart oluşturma."""
        film_kutusu = QWidget()
        width = 180
        height = 310
        film_kutusu.setFixedSize(width, height)
        film_kutusu.setObjectName("ListemKarti")
        
        kutu_layout = QVBoxLayout(film_kutusu)
        kutu_layout.setContentsMargins(8, 8, 8, 8)
        kutu_layout.setAlignment(Qt.AlignTop)
        
        poster_container = QWidget()
        afis_width = 160
        afis_height = 240
        poster_container.setFixedSize(afis_width, afis_height)
        
        p_layout = QVBoxLayout(poster_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        
        afis_label = QLabel()
        afis_label.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(afis_label)
        
        overlay = ListHoverOverlayWidget(poster_container, tmdb_id, title, self, list_type, media_type, poster_path)
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
            self.izlediklerim_grid.addWidget(bos)
            return
        
        for film in izlenenler:
            tmdb_id, title, poster_path, status, rating, review, media_type = film
            kutu = self._liste_karti_olustur(tmdb_id, title, poster_path, status, rating, review, 'izlediklerim', media_type)
            self.izlediklerim_grid.addWidget(kutu)

    def daha_sonra_izle_guncelle(self):
        self.gridi_temizle(self.daha_sonra_grid)
        
        filmler = self.db.kullanicinin_filmlerini_getir(self.user_id)
        izlenecekler = [f for f in filmler if f[3] != "İzlendi"]
        
        if not izlenecekler:
            bos = QLabel("Daha sonra izle listeniz boş.")
            bos.setStyleSheet("font-size: 14px; color: #888; background: transparent;")
            self.daha_sonra_grid.addWidget(bos)
            return
        
        for film in izlenecekler:
            tmdb_id, title, poster_path, status, rating, review, media_type = film
            kutu = self._liste_karti_olustur(tmdb_id, title, poster_path, status, rating, review, 'daha_sonra_izle', media_type)
            self.daha_sonra_grid.addWidget(kutu)

    def listeden_kaldir(self, movie_id, title, list_type):
        cevap = QMessageBox.question(
            self, " Kaldır", 
            f"\"{title}\" listeden kaldırılsın mı?",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap == QMessageBox.Yes:
            self.db.kullanici_film_sil(self.user_id, movie_id)
            if list_type == 'izlediklerim':
                self.izlediklerimi_guncelle()
            else:
                self.daha_sonra_izle_guncelle()
            self.buton_durumlarini_guncelle()

    def buton_durumlarini_guncelle(self):
        for widget in self.findChildren(HoverOverlayWidget):
            if hasattr(widget, 'durum_guncelle'):
                widget.durum_guncelle()
                
        for widget in self.findChildren(FilmKadroPenceresi):
            if hasattr(widget, 'durum_guncelle'):
                widget.durum_guncelle()

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
        
    def arama_metni_degisti(self, metin):
        self.search_timer.stop()
        if not metin.strip():
            self.arama_container.hide()
            self.normal_icerik_container.show()
        else:
            self.search_timer.start(500)
            
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
        media_type = film.get('media_type', 'movie')
        self.db.film_kaydet(film.get('id'), title, film.get('poster_path', ''), media_type)
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
