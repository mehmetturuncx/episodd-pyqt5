import sys
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QGridLayout, QScrollArea, QMessageBox, QTabWidget,
                             QDialog, QComboBox, QSpinBox, QTextEdit, QDesktopWidget, QAction, QGroupBox, QFormLayout)
from PyQt5.QtGui import QPixmap, QFont, QCursor, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, QRect, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint
from api_manager import MovieAPI
from database import DatabaseManager
from PyQt5.QtGui import QPainter, QColor
import qtawesome as qta


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
    data_loaded = pyqtSignal(list, list)
    
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        
    def run(self):
        yeni = self.api.yeni_cikan_filmler()
        top = self.api.en_yuksek_puanli_filmler()
        self.data_loaded.emit(yeni or [], top or [])

class SearchLoader(QThread):
    search_completed = pyqtSignal(list)
    
    def __init__(self, api, query, parent=None):
        super().__init__(parent)
        self.api = api
        self.query = query
        
    def run(self):
        sonuclar = self.api.film_ara(self.query)
        self.search_completed.emit(sonuclar or [])

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

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 episodd")
        self.resize(500, 450)
        self.center()
        
        self.db = DatabaseManager()
        self.arayuzu_hazirla()
        self.temayi_uygula()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def arayuzu_hazirla(self):
        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana_layout = QVBoxLayout(merkez)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        logo_label = QLabel()
        logo_label.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(72, 72))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("margin-bottom: 10px; background: transparent;")
        layout.addWidget(logo_label)

        baslik = QLabel("episodd")
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 40px; color: #ffffff; background: transparent;")
        layout.addWidget(baslik)

        form_layout = QVBoxLayout()
        form_layout.setAlignment(Qt.AlignHCenter)
        
        self.kullanici_input = QLineEdit()
        self.kullanici_input.setPlaceholderText("Kullanıcı Adı")
        self.kullanici_input.setFixedWidth(320)
        self.kullanici_input.setFixedHeight(50)
        form_layout.addWidget(self.kullanici_input)

        self.sifre_input = QLineEdit()
        self.sifre_input.setPlaceholderText("Şifre")
        self.sifre_input.setEchoMode(QLineEdit.Password)
        self.sifre_input.setFixedWidth(320)
        self.sifre_input.setFixedHeight(50)
        form_layout.addWidget(self.sifre_input)

        layout.addLayout(form_layout)

        buton_layout = QHBoxLayout()
        buton_layout.setAlignment(Qt.AlignHCenter)
        
        self.giris_butonu = QPushButton("Giriş Yap")
        self.giris_butonu.setFixedSize(155, 50)
        self.giris_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.giris_butonu.clicked.connect(self.giris_kontrol)
        
        self.kayit_butonu = QPushButton("Kayıt Ol")
        self.kayit_butonu.setFixedSize(155, 50)
        self.kayit_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.kayit_butonu.clicked.connect(self.kayit_ol)

        buton_layout.addWidget(self.giris_butonu)
        buton_layout.addWidget(self.kayit_butonu)
        
        layout.addLayout(buton_layout)
        ana_layout.addLayout(layout)

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
                self.ana_pencere = MovieApp(kullanici_adi, user_id, self.db)
                self.ana_pencere.show()
                self.close()
            else:
                QMessageBox.critical(self, "Hata", "Şifre yanlış!")
        else:
            QMessageBox.critical(self, "Hata", "Kullanıcı bulunamadı!")

    def kayit_ol(self):
        kullanici_adi = self.kullanici_input.text()
        sifre = self.sifre_input.text()

        if not kullanici_adi or not sifre:
            QMessageBox.warning(self, "Hata", "Lütfen tüm alanları doldurun.")
            return

        if self.db.kullanici_ekle(kullanici_adi, sifre):
            QMessageBox.information(self, "Başarılı", "Kayıt oldunuz! Şimdi giriş yapabilirsiniz.")
        else:
            QMessageBox.warning(self, "Hata", "Bu kullanıcı adı zaten alınmış.")

    def temayi_uygula(self):
        koyu_stil = """
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a2e, stop:1 #0f0f17);
        }
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QLineEdit {
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 0 15px;
            color: #FFFFFF;
            font-size: 16px;
            margin-bottom: 10px;
        }
        QLineEdit:focus {
            border: 1px solid #e50914;
            background-color: rgba(255, 255, 255, 0.08);
        }
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e50914, stop:1 #b80710);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f40612, stop:1 #e50914);
        }
        """
        self.setStyleSheet(koyu_stil)

class DegerlendirmePenceresi(QDialog):
    def __init__(self, film_adi, ana_tema):
        super().__init__()
        self.setWindowTitle(f"Değerlendir: {film_adi}")
        self.resize(450, 420)
        self.arayuzu_kur(ana_tema)

    def arayuzu_kur(self, ana_tema):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # İzleme durumu kaldırıldı, değerlendiriliyorsa "İzlendi" kabul edilir

        lbl_puan = QLabel("Puanın (5 Üzerinden):")
        lbl_puan.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(lbl_puan)
        
        self.puan_widget = StarRatingWidget()
        self.puan_widget.setValue(2.5)
        layout.addWidget(self.puan_widget)

        lbl_yorum = QLabel("Yorumun / Analizin:")
        lbl_yorum.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(lbl_yorum)
        
        self.yorum_kutusu = QTextEdit()
        self.yorum_kutusu.setPlaceholderText("Film hakkında ne düşünüyorsun?")
        layout.addWidget(self.yorum_kutusu)

        self.kaydet_butonu = QPushButton("Kaydet")
        self.kaydet_butonu.setObjectName("PrimaryButon")
        self.kaydet_butonu.setFixedHeight(45)
        self.kaydet_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.kaydet_butonu.clicked.connect(self.accept)
        layout.addWidget(self.kaydet_butonu)

        self.setStyleSheet(ana_tema)

    def verileri_al(self):
        return "İzlendi", self.puan_widget.value(), self.yorum_kutusu.toPlainText()

class HoverOverlayWidget(QWidget):
    def __init__(self, parent=None, film=None, main_app=None):
        super().__init__(parent)
        self.film = film
        self.main_app = main_app
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7); border-radius: 8px;")
        
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
        
    def daha_sonra_izle(self):
        self.main_app.listeye_ekle(self.film)
        
    def degerlendir(self):
        movie_id = self.film.get('id')
        title = self.film.get('title') or self.film.get('name', 'Bilinmiyor')
        self.main_app.degerlendirme_ac(movie_id, title)

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
        
        welcome_title = QLabel("Episodd'a\nHoşgeldiniz!")
        welcome_title.setStyleSheet("font-size: 26px; font-weight: bold; margin-bottom: 15px; background: transparent;")
        welcome_title.setAlignment(Qt.AlignCenter)
        
        welcome_text = QLabel("En popüler içerikleri keşfedin,\nlistenizi oluşturun ve\nizlediklerinizi puanlayın.")
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet("font-size: 16px; line-height: 1.5; color: palette(text); background: transparent;")
        welcome_text.setAlignment(Qt.AlignCenter)
        
        welcome_layout.addWidget(welcome_title)
        welcome_layout.addWidget(welcome_text)
        
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
        
        title = film.get('title') or film.get('name', 'Bilinmiyor')
        yil = film.get('release_date') or film.get('first_air_date', ' ')
        
        poster_path = film.get('poster_path')
        if poster_path:
            if not self.afis_label.pixmap():
                self.afis_label.setText("Yükleniyor...")
            
            # Eski indirmeyi iptal etmek yerine sadece arayüzü güncellemesini engelliyoruz
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
        self.setGeometry(100, 100, 1100, 850)
        self.api = MovieAPI()
        self.active_threads = []
        
        
        
        self.arayuzu_hazirla()
        self.temayi_guncelle(self.secili_tema)

    

    def arayuzu_hazirla(self):
        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana_layout = QVBoxLayout(merkez)
        ana_layout.setContentsMargins(0,0,0,0)
        ana_layout.setSpacing(0)

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


        self.sekmeler = QTabWidget()
        self.sekmeler.setObjectName("MainTabs")
        ana_layout.addWidget(self.sekmeler)
        self.sekmeler.setStyleSheet("QTabBar::tab { width: 150px; height: 40px; }")

        self.ana_sekme = QWidget()
        self.liste_sekmesi = QWidget()
        self.ayarlar_sekmesi = QWidget()

        self.sekmeler.addTab(self.ana_sekme, qta.icon('fa5s.home'), " Ana Menü")
        self.sekmeler.addTab(self.liste_sekmesi, qta.icon('fa5s.list'), " Listem")
        self.sekmeler.addTab(self.ayarlar_sekmesi, qta.icon('fa5s.cog'), " Ayarlar")

        self.ana_sekmesini_kur()
        self.liste_sekmesini_kur()
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
        
        baslik2 = QLabel(" En Yüksek Puanlılar")
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
        
        self.icerik_layout.addWidget(self.normal_icerik_container)
        self.icerik_layout.addWidget(self.arama_container)
        self.main_scroll.setWidget(self.icerik_widget)
        self.ana_layout.addWidget(self.main_scroll)

        self.top_layout.addWidget(QLabel("İçerikler yükleniyor..."))

        self.data_loader = DataLoader(self.api, self)
        self.active_threads.append(self.data_loader)
        self.data_loader.data_loaded.connect(self.ana_menu_filmleri_doldur)
        self.data_loader.finished.connect(lambda t=self.data_loader: self.cleanup_thread(t))
        self.data_loader.start()

    def ana_menu_filmleri_doldur(self, yeni_filmler, top_filmler):
        for i in reversed(range(self.top_layout.count())): 
            w = self.top_layout.itemAt(i).widget()
            if w: w.setParent(None)

        if yeni_filmler:
            self.carousel.set_filmler(yeni_filmler)
            
        if top_filmler:
            for film in top_filmler:
                kutu = self.film_karti_olustur(film)
                self.top_layout.addWidget(kutu)
        else:
            self.top_layout.addWidget(QLabel("İçerikler yüklenemedi."))

    def liste_sekmesini_kur(self):
        layout = QVBoxLayout(self.liste_sekmesi)
        layout.setContentsMargins(20, 20, 20, 20)
        
        baslik = QLabel(" Listem")
        baslik.setObjectName("KategoriBaslik")
        layout.addWidget(baslik)

        self.liste_scroll = QScrollArea()
        self.liste_scroll.setWidgetResizable(True)
        self.liste_icerik_widget = QWidget()
        self.liste_icerik_widget.setObjectName("IcerikPaneli")
        self.liste_grid = QGridLayout(self.liste_icerik_widget)
        self.liste_grid.setSpacing(20)
        self.liste_grid.setAlignment(Qt.AlignTop)
        self.liste_scroll.setWidget(self.liste_icerik_widget)
        
        layout.addWidget(self.liste_scroll)

    def ayarlar_sekmesini_kur(self):
        layout = QVBoxLayout(self.ayarlar_sekmesi)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignTop)

        grup = QGroupBox("Hesap ve Tema Ayarları")
        grup.setObjectName("AyarlarGrup")
        form = QFormLayout(grup)
        form.setSpacing(20)
        form.setLabelAlignment(Qt.AlignRight)

        self.ayar_kullanici = QLineEdit(self.username)
        self.ayar_kullanici.setFixedHeight(40)
        self.ayar_sifre = QLineEdit()
        self.ayar_sifre.setPlaceholderText("Değiştirmek istemiyorsanız boş bırakın")
        self.ayar_sifre.setEchoMode(QLineEdit.Password)
        self.ayar_sifre.setFixedHeight(40)

        self.ayar_tema = QComboBox()
        self.ayar_tema.addItems(["Netflix", "IMDb", "Açık Tema"])
        self.ayar_tema.setCurrentText(self.secili_tema)
        self.ayar_tema.setFixedHeight(40)
        self.ayar_tema.currentTextChanged.connect(self.temayi_guncelle)

        kaydet_btn = QPushButton("Değişiklikleri Kaydet")
        kaydet_btn.setObjectName("PrimaryButon")
        kaydet_btn.setFixedHeight(45)
        kaydet_btn.setCursor(QCursor(Qt.PointingHandCursor))
        kaydet_btn.clicked.connect(self.ayarlari_kaydet)

        lbl1 = QLabel("Kullanıcı Adı:")
        lbl2 = QLabel("Yeni Şifre:")
        lbl3 = QLabel("Tema Seçimi:")

        form.addRow(lbl1, self.ayar_kullanici)
        form.addRow(lbl2, self.ayar_sifre)
        form.addRow(lbl3, self.ayar_tema)
        form.addRow("", kaydet_btn)

        layout.addWidget(grup)

    def ayarlari_kaydet(self):
        yeni_ad = self.ayar_kullanici.text()
        yeni_sifre = self.ayar_sifre.text()

        if not yeni_ad:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı boş olamaz.")
            return

        basarili = self.db.kullanici_guncelle(self.user_id, yeni_ad, yeni_sifre)
        if basarili:
            self.username = yeni_ad
            self.kullanici_hosgeldin.setText(f"Hoşgeldin, {self.username}")
            QMessageBox.information(self, "Başarılı", "Bilgileriniz güncellendi.")
            self.ayar_sifre.clear()
        else:
            QMessageBox.warning(self, "Hata", "Bu kullanıcı adı zaten kullanılıyor.")

    def degerlendirme_ac(self, movie_id, title):
        dialog = DegerlendirmePenceresi(title, self.styleSheet())
        if dialog.exec_():
            status, rating, review = dialog.verileri_al()
            self.db.film_degerlendir(self.user_id, movie_id, status, rating, review)
            self.listeyi_guncelle()

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

    def listeyi_guncelle(self):
        for i in reversed(range(self.liste_grid.count())): 
            widget_to_remove = self.liste_grid.itemAt(i).widget()
            if widget_to_remove:
                self.liste_grid.removeWidget(widget_to_remove)
                widget_to_remove.setParent(None)

        filmler = self.db.kullanicinin_filmlerini_getir(self.user_id)
        if not filmler:
            self.liste_grid.addWidget(QLabel("Listen şu an boş."), 0, 0)
            return

        satir, sutun = 0, 0
        max_sutun = 4 

        for film in filmler:
            tmdb_id, title, poster_path, status, rating, review = film
            film_kutusu = QWidget()
            film_kutusu.setFixedSize(220, 380)
            film_kutusu.setObjectName("ListemKarti")
            
            kutu_layout = QVBoxLayout(film_kutusu)
            kutu_layout.setContentsMargins(10, 10, 10, 10)
            
            afis_label = QLabel()
            afis_label.setAlignment(Qt.AlignCenter)
            afis_label.setStyleSheet("background: transparent;")
            if poster_path:
                afis_label.setText("Yükleniyor...")
                afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
                loader = PosterLoader(self.api, poster_path, self)
                self.active_threads.append(loader)
                loader.poster_downloaded.connect(lambda veri, lbl=afis_label: self.afis_yukle(lbl, veri, 140, 210))
                loader.finished.connect(lambda t=loader: self.cleanup_thread(t))
                loader.start()
            else:
                afis_label.setText("Afiş Yok")
                afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            
            baslik_label = QLabel(title)
            baslik_label.setAlignment(Qt.AlignCenter)
            baslik_label.setWordWrap(True)
            baslik_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 5px; background: transparent;")
            
            durum_renk = self.get_status_color(status)
            durum_label = QLabel(f"{status}")
            durum_label.setAlignment(Qt.AlignCenter)
            durum_label.setStyleSheet(f"color: {durum_renk}; font-weight: bold; font-size: 12px; background: rgba(0,0,0,0.2); border-radius: 4px; padding: 2px;")
            
            puan_label = QLabel(self.get_stars_text(rating))
            puan_label.setAlignment(Qt.AlignCenter)
            puan_label.setStyleSheet("color: #f5c518; font-size: 14px; background: transparent;")
            
            yorum_preview = QLabel(f"{review[:30]}..." if review and len(review) > 30 else (review or ""))
            yorum_preview.setAlignment(Qt.AlignCenter)
            yorum_preview.setStyleSheet("color: #888; font-size: 11px; font-style: italic; background: transparent;")

            import qtawesome as qta
            puanla_butonu = QPushButton(" Değerlendir")
            puanla_butonu.setIcon(qta.icon('fa5s.star', color='#f5c518'))
            puanla_butonu.setObjectName("DegerlendirButonu")
            puanla_butonu.setFixedHeight(30)
            puanla_butonu.setCursor(QCursor(Qt.PointingHandCursor))
            puanla_butonu.clicked.connect(lambda checked, m_id=tmdb_id, t=title: self.degerlendirme_ac(m_id, t))
            
            kutu_layout.addWidget(afis_label)
            kutu_layout.addWidget(baslik_label)
            kutu_layout.addWidget(durum_label)
            kutu_layout.addWidget(puan_label)
            kutu_layout.addWidget(yorum_preview)
            kutu_layout.addStretch()
            kutu_layout.addWidget(puanla_butonu)
            
            self.liste_grid.addWidget(film_kutusu, satir, sutun)
            sutun += 1
            if sutun >= max_sutun:
                sutun = 0
                satir += 1

    def sekme_degisti(self, index):
        if index == 1: # Listem is now index 1
            self.listeyi_guncelle()

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
        self.db.film_kaydet(film.get('id'), film.get('title', ''), film.get('poster_path', ''))
        if self.db.kullanici_film_ekle(self.user_id, film.get('id')):
            QMessageBox.information(self, "Başarılı", "Listeye eklendi!")
        else:
            QMessageBox.warning(self, "Uyarı", "Zaten listede.")

    def temayi_guncelle(self, tema_adi):
        self.secili_tema = tema_adi
        
        # Tema Renk Paletleri
        if tema_adi == "Netflix":
            bg_main = "#0a0a0f"
            bg_panel = "#1a1a24"
            bg_hover = "#232330"
            text_main = "#FFFFFF"
            text_sec = "#888888"
            accent = "#e50914"
            accent_hover = "#f40612"
            header_bg = "#111116"
        elif tema_adi == "IMDb":
            bg_main = "#121212"
            bg_panel = "#1f1f1f"
            bg_hover = "#2c2c2c"
            text_main = "#FFFFFF"
            text_sec = "#aaaaaa"
            accent = "#f5c518"
            accent_hover = "#e6b610"
            header_bg = "#000000"
        else: # Açık Tema
            bg_main = "#f4f6f8"
            bg_panel = "#ffffff"
            bg_hover = "#f0f0f0"
            text_main = "#222222"
            text_sec = "#666666"
            accent = "#3498db"
            accent_hover = "#2980b9"
            header_bg = "#ffffff"

        # Accent metin rengi
        accent_text = "#000000" if tema_adi == "IMDb" else "#FFFFFF"

        # Tab ve Buton ikonlarını tema rengine göre güncelle
        self.sekmeler.setTabIcon(0, qta.icon('fa5s.home', color=text_main))
        self.sekmeler.setTabIcon(1, qta.icon('fa5s.list', color=text_main))
        self.sekmeler.setTabIcon(2, qta.icon('fa5s.cog', color=text_main))
        
        self.arama_butonu.setIcon(qta.icon('fa5s.search', color=accent_text))
        self.arama_geri_btn.setIcon(qta.icon('fa5s.arrow-left', color=accent_text))
        if hasattr(self, 'carousel'):
            self.carousel.btn_prev.setIcon(qta.icon('fa5s.chevron-left', color=accent_text))
            self.carousel.btn_next.setIcon(qta.icon('fa5s.chevron-right', color=accent_text))

        stil = f"""
        QMainWindow, QDialog, QScrollArea, QWidget {{ 
            background-color: {bg_main}; 
            color: {text_main}; 
            font-family: 'Segoe UI', Arial; 
        }}
        #AnaMenuIcerik, #IcerikPaneli, #YatayIcerik {{
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
        
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ 
            background: {header_bg}; 
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
            background-color: {bg_main};
        }}
        QTabBar::tab:hover {{ color: {text_main}; }}
        
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
            background-color: {bg_main};
            color: {text_main};
            border: 1px solid {text_sec};
            border-radius: 5px;
        }}
        #DegerlendirButonu:hover {{ border-color: {accent}; color: {accent}; }}
        
        QGroupBox#AyarlarGrup {{
            font-size: 18px;
            font-weight: bold;
            color: {text_main};
            border: 1px solid {text_sec};
            border-radius: 10px;
            margin-top: 20px;
            padding-top: 20px;
            background-color: transparent;
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
        """
        self.setStyleSheet(stil)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = LoginWindow() 
    pencere.show()
    sys.exit(app.exec_())
