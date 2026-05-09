import requests
import os
from dotenv import load_dotenv

load_dotenv()

class MovieAPI:
    def __init__(self):
        self.api_key = os.getenv("TMDB_API_KEY")
        self.base_url = "https://api.themoviedb.org/3"

    def film_ara(self, film_adi):
        url = f"{self.base_url}/search/multi"
        params = {
            "api_key": self.api_key,
            "query": film_adi,
            "language": "en-EN" 
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status() 
            data = response.json()
            
            sonuclar = data.get("results", [])[:10]
            return sonuclar

        except requests.exceptions.RequestException as e:
            print(f"API'ye bağlanırken hata oluştu: {e}")
            return None
            
    def en_yuksek_puanli_filmler(self):
        movie_url = f"{self.base_url}/movie/top_rated"
        tv_url = f"{self.base_url}/tv/top_rated"
        params = {
            "api_key": self.api_key,
            "language": "en-EN",
            "page": 1
        }
        try:
            movie_res = requests.get(movie_url, params=params)
            movie_res.raise_for_status()
            movies = movie_res.json().get("results", [])

            tv_res = requests.get(tv_url, params=params)
            tv_res.raise_for_status()
            tvs = tv_res.json().get("results", [])

            combined = movies + tvs
            combined.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
            return combined[:10]
        except requests.exceptions.RequestException as e:
            print(f"Top Rated API hatası: {e}")
            return []

    def yeni_cikan_filmler(self):
        url = f"{self.base_url}/trending/all/day"
        params = {
            "api_key": self.api_key,
            "language": "en-EN",
            "page": 1
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])[:10]
        except requests.exceptions.RequestException as e:
            print(f"Now Playing API hatası: {e}")
            return []
        
    def poster_indir(self, poster_path):
        if not poster_path:
            return None 
            

        url = f"https://image.tmdb.org/t/p/w200{poster_path}"
        
        try:
            # Görsel verisini indiriyoruz
            response = requests.get(url)
            response.raise_for_status()

            return response.content 
        except requests.exceptions.RequestException:
            return None

if __name__ == "__main__":
    api = MovieAPI()
    aranan_film = "Interstellar"
    print(f"'{aranan_film}' aranıyor...\n")
    
    sonuclar = api.film_ara(aranan_film)
    
    if sonuclar:
        for film in sonuclar:
            print(f"TMDB ID: {film.get('id')}")
            title = film.get('title') or film.get('name', 'Bilinmiyor')
            print(f"Adı: {title}")
            release = film.get('release_date') or film.get('first_air_date', 'Bilinmiyor')
            print(f"Çıkış Tarihi: {release}")
            print(f"Puan: {film.get('vote_average', '0')} / 10")
            print("-" * 30)
    else:
        print("Sonuç bulunamadı. Lütfen API anahtarını doğru girdiğinden emin ol.")