#==============================================================================
# Import and global variables
#==============================================================================
import math
from blist import sortedlist
from sofa.sofa_db import DBManager, Genre

#==============================================================================
# Optimizer class
#==============================================================================

class Recommender():
    def __init__(self, genres=Genre.__genres__):
        self.db_manager = DBManager()
        self.genres = genres
        self.coef = [0.144, 0.187, 0.037, 0.092, 0.095, 0.086, 0.104, 0.032, 
                     0.078, 0.081, 0.063]
    
    @property
    def films(self):
        return self.db_manager.query_films()
    
    def get_ratings(self, titles):
        return self.db_manager.query_films_ratings(titles)
    
    def get_user_classes(self, people):
        return self.db_manager.get_user_classes(people)
    
    def get_people_films(self, people):
        return self.db_manager.get_people_film(people)
        
    def recommend(self, ratings, people):
        genres_ratings = [sum(self.coef[i]*r[i] for r in ratings)
                       for i in range(0, len(self.genres))]
        result = sortedlist([('null', -1)] * 100, key=lambda x: x[1])
        lfilms, dfilms = self.get_people_films(people)
        if len(people)==1:
            banned = [f.id for f in lfilms] + [f.id for f in dfilms]
        else:
            banned = [f.id for f in dfilms]
        session, films = self.films
        for f in films:
            if f.id not in banned:
                frate = sum([float(j)*genres_ratings[i]
                             for i, j in enumerate(f.genres)])
                nb_genres = sum([math.ceil(float(i)) for i in f.genres])
                if nb_genres:
                    frate = frate / nb_genres if nb_genres < 3 else frate / 3
                    if frate > result[0][1]:
                        f.mark = 0
                        result.pop(0)
                        result.add((f, frate))
        session.close()
        user_classes = self.get_user_classes(people)
        films = {f[0].title: f[0] for f in result}
        if len(people) > 1:
            for f in lfilms:
                f.mark = 0
                films[f.title] = f
        session, rtgs = self.get_ratings(films.keys())
        for rtg in rtgs:
            films[rtg.title].mark += user_classes[rtg.class_id]*rtg.rate
        result = [(f.title, f.poster, f.id, f.mark) for f in films.values()]
        result = sorted(result, key=lambda x: x[3])[-10:]
        session.close()
        return list(result)