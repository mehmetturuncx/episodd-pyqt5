import sqlite3
import hashlib

class DatabaseManager:
    def __init__(self, db_name="film_takip.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.tablolari_olustur()

    def tablolari_olustur(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INTEGER PRIMARY KEY, 
                title TEXT NOT NULL,
                poster_path TEXT,
                media_type TEXT DEFAULT 'movie'
            )
        ''')

        try:
            self.cursor.execute("ALTER TABLE movies ADD COLUMN media_type TEXT DEFAULT 'movie'")
        except sqlite3.OperationalError:
            pass

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                movie_id INTEGER,
                status TEXT, 
                rating REAL, 
                review TEXT, 
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(movie_id) REFERENCES movies(tmdb_id)
            )
        ''')
        self.conn.commit()


    def kullanici_ekle(self, username, password):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        try:
            self.cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hashed_pw))
            self.conn.commit()
            print(f"Başarılı: '{username}' kullanıcısı eklendi.")
            return True
        except sqlite3.IntegrityError:
            print("Hata: Bu kullanıcı adı zaten alınmış!")
            return False

    def kullanici_guncelle(self, user_id, yeni_username, yeni_password):
        try:
            if yeni_password:
                hashed_pw = hashlib.sha256(yeni_password.encode()).hexdigest()
                self.cursor.execute('UPDATE users SET username = ?, password_hash = ? WHERE id = ?', (yeni_username, hashed_pw, user_id))
            else:
                self.cursor.execute('UPDATE users SET username = ? WHERE id = ?', (yeni_username, user_id))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
            
    def sifre_dogrula(self, user_id, password):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute("SELECT id FROM users WHERE id = ? AND password_hash = ?", (user_id, hashed_pw))
        return self.cursor.fetchone() is not None

    def kullanici_sil(self, user_id):
        self.cursor.execute("DELETE FROM user_movies WHERE user_id = ?", (user_id,))
        self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
    
    def film_kaydet(self, tmdb_id, title, poster_path, media_type='movie'):
        self.cursor.execute('SELECT tmdb_id FROM movies WHERE tmdb_id = ?', (tmdb_id,))
        if self.cursor.fetchone():
            self.cursor.execute('''
                UPDATE movies SET title = ?, poster_path = ?, media_type = ? WHERE tmdb_id = ?
            ''', (title, poster_path, media_type, tmdb_id))
        else:
            self.cursor.execute('''
                INSERT INTO movies (tmdb_id, title, poster_path, media_type)
                VALUES (?, ?, ?, ?)
            ''', (tmdb_id, title, poster_path, media_type))
        self.conn.commit()

    def kullanici_film_ekle(self, user_id, movie_id, status="izlenecek"):
        self.cursor.execute('''
            SELECT id FROM user_movies WHERE user_id = ? AND movie_id = ?
        ''', (user_id, movie_id))
        
        if self.cursor.fetchone():
            return False 
        
        self.cursor.execute('''
            INSERT INTO user_movies (user_id, movie_id, status)
            VALUES (?, ?, ?)
        ''', (user_id, movie_id, status))
        self.conn.commit()
        return True
    
    def kullanicinin_filmlerini_getir(self, user_id):
        self.cursor.execute('''
            SELECT m.tmdb_id, m.title, m.poster_path, um.status, um.rating, um.review, m.media_type
            FROM movies m
            JOIN user_movies um ON m.tmdb_id = um.movie_id
            WHERE um.user_id = ?
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def film_degerlendir(self, user_id, movie_id, status, rating, review):
        self.cursor.execute('''
            UPDATE user_movies 
            SET status = ?, rating = ?, review = ?
            WHERE user_id = ? AND movie_id = ?
        ''', (status, rating, review, user_id, movie_id))
        self.conn.commit()

    def kullanici_film_sil(self, user_id, movie_id):
        self.cursor.execute('''
            DELETE FROM user_movies 
            WHERE user_id = ? AND movie_id = ?
        ''', (user_id, movie_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def kullanici_film_detay_getir(self, user_id, movie_id):
        self.cursor.execute('''
            SELECT status, rating, review FROM user_movies
            WHERE user_id = ? AND movie_id = ?
        ''', (user_id, movie_id))
        return self.cursor.fetchone()


if __name__ == "__main__":
    db = DatabaseManager()
    print("Veritabanı ve tablolar başarıyla oluşturuldu!")
    
    db.kullanici_ekle("mehmett", "1234")