import requests
import os
from dotenv import load_dotenv

load_dotenv()

class MovieAPI:
    def __init__(self):
        self.api_key = os.getenv("TMDB_API_KEY")
        self.omdb_api_key = os.getenv("OMDB_API_KEY")
        self.base_url = "https://api.themoviedb.org/3"

    def _get_lang_code(self):
        return "tr-TR"

    def film_ara(self, film_adi):
        url = f"{self.base_url}/search/multi"
        params = {
            "api_key": self.api_key,
            "query": film_adi,
            "language": self._get_lang_code() 
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
        params = {
            "api_key": self.api_key,
            "language": self._get_lang_code(),
            "page": 1
        }
        try:
            movie_res = requests.get(movie_url, params=params)
            movie_res.raise_for_status()
            movies = movie_res.json().get("results", [])
            for m in movies: m['media_type'] = 'movie'
            return movies[:10]
        except requests.exceptions.RequestException as e:
            print(f"Top Rated API hatası: {e}")
            return []

    def en_yuksek_puanli_diziler(self):
        tv_url = f"{self.base_url}/tv/top_rated"
        params = {
            "api_key": self.api_key,
            "language": self._get_lang_code(),
            "page": 1
        }
        try:
            tv_res = requests.get(tv_url, params=params)
            tv_res.raise_for_status()
            tvs = tv_res.json().get("results", [])
            for t in tvs: t['media_type'] = 'tv'
            return tvs[:10]
        except requests.exceptions.RequestException as e:
            print(f"Top Rated API hatası: {e}")
            return []

    def yeni_cikan_filmler(self):
        url = f"{self.base_url}/trending/all/day"
        params = {
            "api_key": self.api_key,
            "language": self._get_lang_code(),
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
        
    def film_detay_ve_kredileri(self, film_id, media_type="movie"):
        if not media_type:
            media_type = "movie"
        url = f"{self.base_url}/{media_type}/{film_id}"
        params = {
            "api_key": self.api_key,
            "language": self._get_lang_code(),
            "append_to_response": "credits,external_ids"
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            credits = data.get("credits", {})
            cast = credits.get("cast", [])[:6]
            crew = credits.get("crew", [])
            directors = [c for c in crew if c.get("job") == "Director"][:2]
            return data, cast, directors
        except requests.exceptions.RequestException as e:
            print(f"Details API hatası: {e}")
            return {}, [], []

    def dizi_sezon_getir(self, series_id, season_number):
        url = f"{self.base_url}/tv/{series_id}/season/{season_number}"
        params = {
            "api_key": self.api_key,
            "language": self._get_lang_code()
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Season API hatası (S{season_number}): {e}")
            return {}

    def omdb_sezon_getir(self, imdb_id, season_number):
        if not self.omdb_api_key: return {}
        url = "http://www.omdbapi.com/"
        params = {
            "i": imdb_id,
            "Season": season_number,
            "apikey": self.omdb_api_key
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"OMDB Season API hatası (S{season_number}): {e}")
            return {}

    def poster_indir(self, poster_path):
        if not poster_path:
            return None 
            

        url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        
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