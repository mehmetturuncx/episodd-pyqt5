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
                poster_path TEXT
            )
        ''')

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
    
    def film_kaydet(self, tmdb_id, title, poster_path):
        self.cursor.execute('''
            INSERT OR IGNORE INTO movies (tmdb_id, title, poster_path)
            VALUES (?, ?, ?)
        ''', (tmdb_id, title, poster_path))
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
            SELECT m.tmdb_id, m.title, m.poster_path, um.status, um.rating, um.review
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


if __name__ == "__main__":
    db = DatabaseManager()
    print("Veritabanı ve tablolar başarıyla oluşturuldu!")
    
    db.kullanici_ekle("mehmet", "sifre123")