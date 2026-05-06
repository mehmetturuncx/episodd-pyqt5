import sys
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QGridLayout, QScrollArea, QMessageBox, QTabWidget,
                             QDialog, QComboBox, QSpinBox, QTextEdit, QDesktopWidget, QAction, QGroupBox, QFormLayout)
from PyQt5.QtGui import QPixmap, QFont, QCursor, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from api_manager import MovieAPI
from database import DatabaseManager

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
    ratingChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._rating = 0
        self._hover_rating = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        self.stars = []
        for i in range(1, 6):
            lbl = QLabel("☆")
            lbl.setStyleSheet("color: #f5c518; font-size: 28px;")
            lbl.setCursor(QCursor(Qt.PointingHandCursor))
            lbl.mousePressEvent = lambda e, val=i: self.set_rating(val)
            lbl.enterEvent = lambda e, val=i: self.set_hover(val)
            lbl.leaveEvent = lambda e: self.clear_hover()
            self.stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()

    def set_rating(self, val):
        self._rating = val
        self.update_stars()
        self.ratingChanged.emit(self.value())

    def set_hover(self, val):
        self._hover_rating = val
        self.update_stars()

    def clear_hover(self):
        self._hover_rating = 0
        self.update_stars()

    def update_stars(self):
        val = self._hover_rating if self._hover_rating > 0 else self._rating
        for i, lbl in enumerate(self.stars):
            if i < val:
                lbl.setText("★")
            else:
                lbl.setText("☆")
                
    def value(self):
        return self._rating * 2  

    def setValue(self, val):
        self._rating = val // 2
        self.update_stars()

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 Movied")
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

        logo_label = QLabel("🎬")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("font-size: 72px; margin-bottom: 10px; background: transparent;")
        layout.addWidget(logo_label)

        baslik = QLabel("Movied")
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

        lbl_durum = QLabel("İzleme Durumu:")
        lbl_durum.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(lbl_durum)
        
        self.durum_kutusu = QComboBox()
        self.durum_kutusu.addItems(["İzlenecek", "İzlendi", "Yarım Bırakıldı"])
        self.durum_kutusu.setFixedHeight(40)
        layout.addWidget(self.durum_kutusu)

        lbl_puan = QLabel("Puanın (10 Üzerinden):")
        lbl_puan.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(lbl_puan)
        
        self.puan_widget = StarRatingWidget()
        self.puan_widget.setValue(5)
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
        return self.durum_kutusu.currentText(), self.puan_widget.value(), self.yorum_kutusu.toPlainText()

class MovieApp(QMainWindow):
    def __init__(self, username, user_id, db_manager):
        super().__init__()
        self.username = username
        self.user_id = user_id
        self.db = db_manager 
        self.secili_tema = "Netflix" # Default tema
        
        self.setWindowTitle("Movied")
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
        
        logo = QLabel("🎬 Movied")
        logo.setObjectName("HeaderLogo")
        logo.setStyleSheet("font-size: 26px; font-weight: bold; background: transparent;")
        
        self.kullanici_hosgeldin = QLabel(f"Hoşgeldin, {self.username}")
        self.kullanici_hosgeldin.setObjectName("HeaderUser")
        self.kullanici_hosgeldin.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        
        header_layout.addWidget(logo)
        header_layout.addStretch()
        header_layout.addWidget(self.kullanici_hosgeldin)

        ana_layout.addWidget(self.header)


        self.sekmeler = QTabWidget()
        self.sekmeler.setObjectName("MainTabs")
        ana_layout.addWidget(self.sekmeler)
        self.sekmeler.setStyleSheet("QTabBar::tab { width: 150px; height: 40px; }")

        self.ana_sekme = QWidget()
        self.arama_sekmesi = QWidget()
        self.liste_sekmesi = QWidget()
        self.ayarlar_sekmesi = QWidget()

        self.sekmeler.addTab(self.ana_sekme, "🏠 Ana Menü")
        self.sekmeler.addTab(self.arama_sekmesi, "🔍 Film Ara")
        self.sekmeler.addTab(self.liste_sekmesi, "⭐ Listem")
        self.sekmeler.addTab(self.ayarlar_sekmesi, "⚙️ Ayarlar")

        self.ana_sekmesini_kur()
        self.arama_sekmesini_kur()
        self.liste_sekmesini_kur()
        self.ayarlar_sekmesini_kur()

        self.sekmeler.currentChanged.connect(self.sekme_degisti)

    def film_karti_olustur(self, film):
        film_kutusu = QWidget()
        film_kutusu.setFixedSize(180, 310)
        film_kutusu.setObjectName("FilmKarti")
        
        kutu_layout = QVBoxLayout(film_kutusu)
        kutu_layout.setContentsMargins(8, 8, 8, 8)
        
        afis_label = QLabel()
        afis_label.setAlignment(Qt.AlignCenter)
        afis_label.setStyleSheet("background: transparent;")
        poster_path = film.get('poster_path')
        if poster_path:
            afis_label.setText("Yükleniyor...")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            loader = PosterLoader(self.api, poster_path, self)
            self.active_threads.append(loader)
            loader.poster_downloaded.connect(lambda veri, lbl=afis_label: self.afis_yukle(lbl, veri, 130, 195))
            loader.finished.connect(lambda t=loader: self.cleanup_thread(t))
            loader.start()
        else:
            afis_label.setText("Afiş Yok")
            afis_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        
        yil = film.get('release_date', ' ')[:4]
        baslik = film.get('title', 'Bilinmiyor')
        if len(baslik) > 18: baslik = baslik[:16] + "..."
        bilgi_label = QLabel(f"{baslik}\n({yil})")
        bilgi_label.setAlignment(Qt.AlignCenter)
        bilgi_label.setStyleSheet("font-size: 13px; font-weight: bold; margin-top: 4px; background: transparent;")
        
        ekle_butonu = QPushButton("+ Listeye Ekle")
        ekle_butonu.setObjectName("EkleButonu")
        ekle_butonu.setFixedHeight(28)
        ekle_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        ekle_butonu.clicked.connect(lambda checked, f=film: self.listeye_ekle(f))
        
        kutu_layout.addWidget(afis_label)
        kutu_layout.addWidget(bilgi_label)
        kutu_layout.addStretch()
        kutu_layout.addWidget(ekle_butonu)
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
        layout = QVBoxLayout(self.ana_sekme)
        layout.setContentsMargins(20, 20, 20, 20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("AnaMenuScroll")
        icerik = QWidget()
        icerik.setObjectName("AnaMenuIcerik")
        icerik_layout = QVBoxLayout(icerik)
        
        baslik1 = QLabel("🔥 Yeni Çıkan Filmler")
        baslik1.setObjectName("KategoriBaslik")
        icerik_layout.addWidget(baslik1)
        
        yeni_scroll = QScrollArea()
        yeni_scroll.setFixedHeight(340)
        yeni_scroll.setWidgetResizable(True)
        yeni_icerik = QWidget()
        yeni_icerik.setObjectName("YatayIcerik")
        self.yeni_layout = QHBoxLayout(yeni_icerik)
        self.yeni_layout.setAlignment(Qt.AlignLeft)
        yeni_scroll.setWidget(yeni_icerik)
        icerik_layout.addWidget(yeni_scroll)

        baslik2 = QLabel("🌟 En Yüksek Puanlılar (IMDb Top)")
        baslik2.setObjectName("KategoriBaslik")
        icerik_layout.addWidget(baslik2)
        
        top_scroll = QScrollArea()
        top_scroll.setFixedHeight(340)
        top_scroll.setWidgetResizable(True)
        top_icerik = QWidget()
        top_icerik.setObjectName("YatayIcerik")
        self.top_layout = QHBoxLayout(top_icerik)
        self.top_layout.setAlignment(Qt.AlignLeft)
        top_scroll.setWidget(top_icerik)
        icerik_layout.addWidget(top_scroll)
        
        scroll.setWidget(icerik)
        layout.addWidget(scroll)

        self.yeni_layout.addWidget(QLabel("Filmler yükleniyor..."))
        self.top_layout.addWidget(QLabel("Filmler yükleniyor..."))

        self.data_loader = DataLoader(self.api, self)
        self.active_threads.append(self.data_loader)
        self.data_loader.data_loaded.connect(self.ana_menu_filmleri_doldur)
        self.data_loader.finished.connect(lambda t=self.data_loader: self.cleanup_thread(t))
        self.data_loader.start()

    def ana_menu_filmleri_doldur(self, yeni_filmler, top_filmler):
        for i in reversed(range(self.yeni_layout.count())): 
            w = self.yeni_layout.itemAt(i).widget()
            if w: w.setParent(None)
        for i in reversed(range(self.top_layout.count())): 
            w = self.top_layout.itemAt(i).widget()
            if w: w.setParent(None)

        if yeni_filmler:
            for film in yeni_filmler:
                kutu = self.film_karti_olustur(film)
                self.yeni_layout.addWidget(kutu)
        else:
            self.yeni_layout.addWidget(QLabel("Filmler yüklenemedi."))
            
        if top_filmler:
            for film in top_filmler:
                kutu = self.film_karti_olustur(film)
                self.top_layout.addWidget(kutu)
        else:
            self.top_layout.addWidget(QLabel("Filmler yüklenemedi."))

    def arama_sekmesini_kur(self):
        ana_layout = QVBoxLayout(self.arama_sekmesi)
        ana_layout.setContentsMargins(20, 20, 20, 20)

        arama_layout = QHBoxLayout()
        self.arama_kutusu = QLineEdit()
        self.arama_kutusu.setPlaceholderText("Film adı girin...")
        self.arama_kutusu.setFixedHeight(45)
        self.arama_butonu = QPushButton("Ara")
        self.arama_butonu.setFixedSize(120, 45)
        self.arama_butonu.setCursor(QCursor(Qt.PointingHandCursor))
        self.arama_butonu.setObjectName("PrimaryButon")
        self.arama_butonu.clicked.connect(self.arama_yap)
        self.arama_kutusu.returnPressed.connect(self.arama_yap)
        
        arama_layout.addWidget(self.arama_kutusu)
        arama_layout.addWidget(self.arama_butonu)
        ana_layout.addLayout(arama_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.sonuc_widget = QWidget()
        self.sonuc_widget.setObjectName("IcerikPaneli")
        self.grid_layout = QGridLayout(self.sonuc_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.sonuc_widget)
        ana_layout.addWidget(self.scroll_area)

    def liste_sekmesini_kur(self):
        layout = QVBoxLayout(self.liste_sekmesi)
        layout.setContentsMargins(20, 20, 20, 20)
        
        baslik = QLabel("⭐ Kaydettiğin Filmler")
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
        r = int(rating // 2)
        return ("★" * r) + ("☆" * (5 - r))

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
            puan_label.setStyleSheet("color: #f5c518; font-size: 16px; background: transparent;")
            
            yorum_preview = QLabel(f"{review[:30]}..." if review and len(review) > 30 else (review or ""))
            yorum_preview.setAlignment(Qt.AlignCenter)
            yorum_preview.setStyleSheet("color: #888; font-size: 11px; font-style: italic; background: transparent;")

            puanla_butonu = QPushButton("Değerlendir")
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
        if index == 2: # Listem
            self.listeyi_guncelle()

    def gridi_temizle(self):
        for i in reversed(range(self.grid_layout.count())): 
            w = self.grid_layout.itemAt(i).widget()
            if w:
                self.grid_layout.removeWidget(w)
                w.setParent(None)

    def arama_yap(self):
        aranan = self.arama_kutusu.text()
        if not aranan: return
        self.gridi_temizle()
        QApplication.processEvents()
        
        lbl = QLabel("Aranıyor...")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        self.grid_layout.addWidget(lbl, 0, 0)
        
        self.arama_butonu.setEnabled(False)
        self.search_loader = SearchLoader(self.api, aranan, self)
        self.active_threads.append(self.search_loader)
        self.search_loader.search_completed.connect(self.arama_sonuclarini_goster)
        self.search_loader.finished.connect(lambda t=self.search_loader: self.cleanup_thread(t))
        self.search_loader.start()

    def arama_sonuclarini_goster(self, sonuclar):
        self.arama_butonu.setEnabled(True)
        self.gridi_temizle()
        
        if sonuclar:
            satir, sutun = 0, 0
            for film in sonuclar:
                kutu = self.film_karti_olustur(film)
                self.grid_layout.addWidget(kutu, satir, sutun)
                sutun += 1
                if sutun >= 5:
                    sutun = 0; satir += 1
        else:
            self.grid_layout.addWidget(QLabel("Sonuç bulunamadı."), 0, 0)

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
