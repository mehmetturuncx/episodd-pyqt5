# Episodd - Film ve Dizi Takip Uygulaması

Episodd, kullanıcıların favori filmlerini ve dizilerini takip edebileceği, yeni içerikler keşfedebileceği ve izledikleri yapımlara puan verip inceleme yazabileceği modern arayüzlü bir masaüstü uygulamasıdır. PyQt5 kullanılarak geliştirilmiştir ve gücünü TMDB (The Movie Database) ile OMDB API'lerinden alır.

## 🚀 Özellikler

- **Çoklu Kullanıcı Desteği:** Kendinize özel hesap oluşturarak (kayıt/giriş) verilerinizi kişiselleştirebilirsiniz. Güvenli parola şifrelemesi (SHA-256) kullanır.
- **Kapsamlı Arama:** Filmleri ve dizileri detaylı bir şekilde arayabilirsiniz.
- **Gündem ve Popüler İçerikler:** Yeni çıkan (trend olan) yapımları, en yüksek puanlı filmleri ve dizileri görüntüleyebilirsiniz.
- **Detaylı Bilgiler:** Yapımların oyuncu kadrosu, yönetmenleri, afişleri ve detaylı açıklamalarını görebilirsiniz.
- **Dizi Sezon Bilgileri:** Dizilerin sezonlarına ve bölümlerine ait detaylara erişim sağlayabilirsiniz. Bölüm bazlı IMDB puanı desteği (OMDB API ile) mevcuttur.
- **İzleme Listesi Yönetimi:** Yapımları "İzlenecek", "İzlendi" gibi durumlarla kişisel listenize ekleyebilirsiniz.
- **Kişisel Değerlendirme:** İzlediğiniz yapımlara yıldız sistemi (Star Rating) ile puan verebilir ve kendi incelemenizi/notunuzu yazabilirsiniz.
- **Modern Arayüz:** PyQt5 ile geliştirilmiş, akıcı geçiş animasyonlarına ve kullanıcı dostu bir masaüstü tasarımına sahiptir.

## 🛠️ Kullanılan Teknolojiler

- **Python 3.x**
- **PyQt5 & qtawesome:** Grafiksel kullanıcı arayüzü (GUI) ve ikon yönetimi
- **SQLite3:** Yerel veritabanı yönetimi
- **Requests:** API üzerinden veri çekme işlemleri
- **TMDB API & OMDB API:** Film/Dizi veritabanı sağlayıcıları
- **python-dotenv:** Güvenli ortam değişkenleri (.env) yönetimi

## 📦 Kurulum ve Çalıştırma

Projeyi bilgisayarınıza kurmak ve çalıştırmak için aşağıdaki adımları izleyin:

1. **Depoyu Klonlayın veya İndirin:**
   ```bash
   git clone https://github.com/mehmetturuncx/episodd-pyqt5.git
   cd episodd-pyqt5
   ```

2. **Gerekli Kütüphaneleri Yükleyin:**
   Terminal veya komut satırınızda projenin ana dizinindeyken aşağıdaki komutu çalıştırarak gerekli paketleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. **API Anahtarlarını Ayarlayın:**
   Proje ana dizininde bulunan `.env` dosyasını kendi API anahtarlarınızla güncelleyin (Eğer yoksa yeni bir `.env` dosyası oluşturun):
   ```env
   TMDB_API_KEY=sizin_tmdb_api_anahtariniz
   OMDB_API_KEY=sizin_omdb_api_anahtariniz
   ```
   *(OMDB API anahtarı, dizilerde IMDB puanlarını görebilmek için opsiyonel olarak kullanılabilir.)*

4. **Uygulamayı Başlatın:**
   Her şey hazır! Uygulamayı çalıştırmak için ana dizinde şu komutu girin:
   ```bash
   python main.py
   ```

## 🗄️ Veritabanı Mimarisi (`film_takip.db`)

Uygulama çalıştırıldığında yerel olarak `film_takip.db` isimli bir SQLite veritabanı oluşturulur. Bu veritabanı aşağıdaki tablolardan oluşur:
- **`users`:** Kullanıcıların giriş bilgilerini (kullanıcı adı ve şifrelenmiş parola) depolar.
- **`movies`:** İzleme listelerine eklenen yapımların (Film veya Dizi) TMDB kimliği, adı, afiş yolu ve medya türü gibi önbelleklenmiş temel bilgilerini tutar.
- **`user_movies`:** Kullanıcılar ile yapımlar arasındaki ilişkiyi kurar. Hangi kullanıcının hangi yapımı ne durumda (İzlendi vs.) eklediğini, verdiği puanı ve yazdığı incelemeyi depolar.

## 🤝 Katkıda Bulunma

Geliştirmelere, hata düzeltmelerine ve yeni özellik önerilerine her zaman açığız. Katkıda bulunmak isterseniz lütfen bir "Pull Request" oluşturun veya sorun (issue) bildirerek iletişime geçin.
