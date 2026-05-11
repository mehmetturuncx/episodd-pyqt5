import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add qtawesome
content = content.replace('from PyQt5.QtGui import QPainter, QColor', 'from PyQt5.QtGui import QPainter, QColor\nimport qtawesome as qta')

# 2. Login Window logo
old_login_logo = '''        logo_label = QLabel("🎬")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("font-size: 72px; margin-bottom: 10px; background: transparent;")'''
new_login_logo = '''        logo_label = QLabel()
        logo_label.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(72, 72))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("margin-bottom: 10px; background: transparent;")'''
content = content.replace(old_login_logo, new_login_logo)

# 3. Add HoverOverlayWidget and CarouselWidget before MovieApp
new_widgets = '''class HoverOverlayWidget(QWidget):
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
        layout.setAlignment(Qt.AlignCenter)
        
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
        self.poster_container.setFixedSize(300, 450)
        p_layout = QVBoxLayout(self.poster_container)
        p_layout.setContentsMargins(0,0,0,0)
        self.afis_label = QLabel()
        self.afis_label.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(self.afis_label)
        
        self.overlay = HoverOverlayWidget(self.poster_container, None, self.main_app)
        self.overlay.setFixedSize(300, 450)
        
        def enter_event(e): self.overlay.show()
        def leave_event(e): self.overlay.hide()
        self.poster_container.enterEvent = enter_event
        self.poster_container.leaveEvent = leave_event
        
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-top: 10px;")
        
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.poster_container)
        center_layout.addWidget(self.info_label)
        
        layout.addWidget(self.btn_prev)
        layout.addLayout(center_layout)
        layout.addWidget(self.btn_next)
        
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
        self.current_idx = (self.current_idx - 1) % len(self.filmler)
        self.update_ui()
        self.timer.start(5000)
        
    def next_film(self):
        if not self.filmler: return
        self.current_idx = (self.current_idx + 1) % len(self.filmler)
        self.update_ui()
        self.timer.start(5000)
        
    def update_ui(self):
        if not self.filmler: return
        film = self.filmler[self.current_idx]
        self.overlay.film = film
        self.overlay.hide()
        
        title = film.get('title') or film.get('name', 'Bilinmiyor')
        yil = film.get('release_date') or film.get('first_air_date', ' ')
        self.info_label.setText(f"{title} ({yil[:4]})")
        
        poster_path = film.get('poster_path')
        if poster_path:
            self.afis_label.setText("Yükleniyor...")
            if self.active_loader:
                self.active_loader.deleteLater()
            self.active_loader = PosterLoader(self.api, poster_path, self)
            self.active_loader.poster_downloaded.connect(self.afis_yukle)
            self.active_loader.start()
        else:
            self.afis_label.setText("Afiş Yok")
            
    def afis_yukle(self, veri):
        pixmap = QPixmap()
        if pixmap.loadFromData(veri):
            self.afis_label.setPixmap(pixmap.scaled(300, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation))

class MovieApp'''
content = content.replace('class MovieApp', new_widgets)

# 4. Remove scroll_timer from MovieApp
content = re.sub(r'self\.scroll_timer = QTimer\(self\).*?self\.scroll_timer\.start\(40\)', '', content, flags=re.DOTALL)
content = re.sub(r'def auto_scroll_yeni\(self\):.*?scrollbar\.setValue\(0\)', '', content, flags=re.DOTALL)

# 5. Header Icons
old_header = '''        logo = QLabel("🎬 episodd")
        logo.setObjectName("HeaderLogo")
        logo.setStyleSheet("font-size: 26px; font-weight: bold; background: transparent;")'''
new_header = '''        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon('fa5s.film', color='#e50914').pixmap(30, 30))
        logo = QLabel(" episodd")
        logo.setObjectName("HeaderLogo")
        logo.setStyleSheet("font-size: 26px; font-weight: bold; background: transparent;")
        
        header_h = QHBoxLayout()
        header_h.addWidget(logo_icon)
        header_h.addWidget(logo)'''
content = content.replace(old_header, new_header)
content = content.replace('header_layout.addWidget(logo)', 'header_layout.addLayout(header_h)')

# 6. Tabs
old_tabs = '''        self.ana_sekme = QWidget()
        self.arama_sekmesi = QWidget()
        self.liste_sekmesi = QWidget()
        self.ayarlar_sekmesi = QWidget()

        self.sekmeler.addTab(self.ana_sekme, "🏠 Ana Menü")
        self.sekmeler.addTab(self.arama_sekmesi, "🔍 Ara")
        self.sekmeler.addTab(self.liste_sekmesi, "⭐ Listem")
        self.sekmeler.addTab(self.ayarlar_sekmesi, "⚙️ Ayarlar")

        self.ana_sekmesini_kur()
        self.arama_sekmesini_kur()
        self.liste_sekmesini_kur()
        self.ayarlar_sekmesini_kur()'''
new_tabs = '''        self.ana_sekme = QWidget()
        self.liste_sekmesi = QWidget()
        self.ayarlar_sekmesi = QWidget()

        self.sekmeler.addTab(self.ana_sekme, qta.icon('fa5s.home'), " Ana Menü")
        self.sekmeler.addTab(self.liste_sekmesi, qta.icon('fa5s.list'), " Listem")
        self.sekmeler.addTab(self.ayarlar_sekmesi, qta.icon('fa5s.cog'), " Ayarlar")

        self.ana_sekmesini_kur()
        self.liste_sekmesini_kur()
        self.ayarlar_sekmesini_kur()'''
content = content.replace(old_tabs, new_tabs)

# 7. film_karti_olustur (removing button, adding hover overlay)
old_film_karti = '''    def film_karti_olustur(self, film, is_large=False):
        film_kutusu = QWidget()
        
        width = 240 if is_large else 180
        height = 380 if is_large else 310
        film_kutusu.setFixedSize(width, height)
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
            
            afis_width = 210 if is_large else 130
            afis_height = 315 if is_large else 195
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
        bilgi_label = QLabel(f"{baslik}\\n({yil})")
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
        return film_kutusu'''

new_film_karti = '''    def film_karti_olustur(self, film, is_large=False):
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
        bilgi_label = QLabel(f"{baslik}\\n({yil})")
        bilgi_label.setAlignment(Qt.AlignCenter)
        bilgi_label.setStyleSheet("font-size: 13px; font-weight: bold; margin-top: 4px; background: transparent;")
        
        kutu_layout.addWidget(poster_container)
        kutu_layout.addStretch()
        kutu_layout.addWidget(bilgi_label)
        return film_kutusu'''
content = content.replace(old_film_karti, new_film_karti)

# 8. ana_sekmesini_kur
old_ana_sekme = '''    def ana_sekmesini_kur(self):
        layout = QVBoxLayout(self.ana_sekme)
        layout.setContentsMargins(20, 20, 20, 20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("AnaMenuScroll")
        icerik = QWidget()
        icerik.setObjectName("AnaMenuIcerik")
        icerik_layout = QVBoxLayout(icerik)
        
        baslik1 = QLabel("🔥 Yeni Çıkanlar")
        baslik1.setObjectName("KategoriBaslik")
        icerik_layout.addWidget(baslik1)
        
        self.yeni_scroll = QScrollArea()
        self.yeni_scroll.setFixedHeight(410)
        self.yeni_scroll.setWidgetResizable(True)
        yeni_icerik = QWidget()
        yeni_icerik.setObjectName("YatayIcerik")
        self.yeni_layout = QHBoxLayout(yeni_icerik)
        self.yeni_layout.setAlignment(Qt.AlignLeft)
        self.yeni_scroll.setWidget(yeni_icerik)
        icerik_layout.addWidget(self.yeni_scroll)

        baslik2 = QLabel("🌟 En Yüksek Puanlılar")
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

        self.yeni_layout.addWidget(QLabel("İçerikler yükleniyor..."))
        self.top_layout.addWidget(QLabel("İçerikler yükleniyor..."))

        self.data_loader = DataLoader(self.api, self)
        self.active_threads.append(self.data_loader)
        self.data_loader.data_loaded.connect(self.ana_menu_filmleri_doldur)
        self.data_loader.finished.connect(lambda t=self.data_loader: self.cleanup_thread(t))
        self.data_loader.start()'''

new_ana_sekme = '''    def ana_sekmesini_kur(self):
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
        self.arama_grid.setAlignment(Qt.AlignTop)
        
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
        self.data_loader.start()'''
content = content.replace(old_ana_sekme, new_ana_sekme)

# 9. ana_menu_filmleri_doldur
old_doldur = '''    def ana_menu_filmleri_doldur(self, yeni_filmler, top_filmler):
        for i in reversed(range(self.yeni_layout.count())): 
            w = self.yeni_layout.itemAt(i).widget()
            if w: w.setParent(None)
        for i in reversed(range(self.top_layout.count())): 
            w = self.top_layout.itemAt(i).widget()
            if w: w.setParent(None)

        if yeni_filmler:
            for film in yeni_filmler:
                kutu = self.film_karti_olustur(film, is_large=True)
                self.yeni_layout.addWidget(kutu)
        else:
            self.yeni_layout.addWidget(QLabel("İçerikler yüklenemedi."))
            
        if top_filmler:
            for film in top_filmler:
                kutu = self.film_karti_olustur(film)
                self.top_layout.addWidget(kutu)
        else:
            self.top_layout.addWidget(QLabel("İçerikler yüklenemedi."))'''
new_doldur = '''    def ana_menu_filmleri_doldur(self, yeni_filmler, top_filmler):
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
            self.top_layout.addWidget(QLabel("İçerikler yüklenemedi."))'''
content = content.replace(old_doldur, new_doldur)

# 10. arama_sekmesini_kur ve arama_yap
content = re.sub(r'def arama_sekmesini_kur\(self\):.*?def liste_sekmesini_kur\(self\):', 'def liste_sekmesini_kur(self):', content, flags=re.DOTALL)

old_arama_methods = '''    def gridi_temizle(self):
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
            self.grid_layout.addWidget(QLabel("Sonuç bulunamadı."), 0, 0)'''
            
new_arama_methods = '''    def gridi_temizle(self, grid):
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
                if sutun >= 5:
                    sutun = 0; satir += 1
        else:
            self.arama_grid.addWidget(QLabel("Sonuç bulunamadı."), 0, 0)'''
content = content.replace(old_arama_methods, new_arama_methods)

# 11. sekme_degisti remove index 2 logic
content = content.replace('''    def sekme_degisti(self, index):
        if index == 2: # Listem
            self.listeyi_guncelle()''', '''    def sekme_degisti(self, index):
        if index == 1: # Listem is now index 1
            self.listeyi_guncelle()''')

# 12. Emojis in titles:
content = content.replace(' baslik = QLabel("⭐ Listem")', ' baslik = QLabel(" Listem")')
content = content.replace('baslik = QLabel("⭐ Listem")', 'baslik = QLabel(" Listem")')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
