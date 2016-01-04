import os
import sys
import csv
import sqlalchemy
from sqlalchemy import Column, create_engine, ForeignKey
from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session, relationship, backref, joinedload_all
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError
from  sqlalchemy.sql.expression import func
from collections import defaultdict

if __name__ == "__main__":
    module_dir = os.path.dirname(sys.argv[0])
else:
    module_dir = os.path.dirname(__file__)

delimiter = ';'

HOST = 'sofadb'
USER = 'usr'
PASSWORD = 'pwd'
DATABASE = 'SofaDB'

Base = declarative_base()

class UserClass(Base):
    __tablename__ = 'user_classes'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "User(id=%r)" % self.id


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), primary_key=True, unique=True, index=True)
    pwd = Column(String(50), nullable=False)
    class_ids = Column(ARRAY(Integer),  default=[(0,1)])
    pending = Column(ARRAY(Integer), default=[])
    liked = Column(ARRAY(Integer), default=[])
    unliked = Column(ARRAY(Integer), default=[])
    favorite = Column(ARRAY(Integer), default=[])
    follower = Column(ARRAY(String(150)), default=[])
    followed = Column(ARRAY(String(150)), default=[])

    def __init__(self, name, pwd):
        self.name = name
        self.pwd = pwd

    def __repr__(self):
        return "User(name=%r)" % self.name
        

class Genre(Base):
    __tablename__ = 'genres'
    __genres__ = ['Action', 'Adventure', 'Animation', 'Comedy', 'Drama',
                  'Family', 'Fantasy', 'Mystery', 'Romance', 'Science Fiction',
                  'Thriller']
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    
    def __init__(self, name):
        self.name = name       

    def __repr__(self):
        return "Genre(name=%r)" % self.name


class Film(Base):
    __tablename__ = 'films'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), index=True, nullable=False)
    genres_id = Column(ARRAY(Integer), default=[])
    poster = Column(String(300), nullable=False)
    rating = Column(Float)
    date = Column(String(50), index=True)
    actors = Column(ARRAY(String(50)), default=[], index=True)
    directors = Column(ARRAY(String(50)), default=[], index=True)
    netflix_id = Column(String(180))
    trailer = Column(String(400))
    runtime = Column(Integer, index=True)
    descr = Column(String(500))
    
    def __init__(self, title, poster, **kwargs):
        self.title = title
        self.poster = poster
        for k, v in kwargs.items():
            setattr(self, k, v)  
        
    @property
    def genres(self):
        if not hasattr(self, '_genres'):
            nb_genres = len(Genre.__genres__)
            setattr(self, '_genres', [1 if i in self.genres_id else 0
                                      for i in range(1, nb_genres + 1)])
        return self._genres    
    
    @property
    def genre_names(self):
        if not hasattr(self, '_genre_names'):
            gnames = []
            for i, g in enumerate(self.genres):
                if g: gnames.append(Genre.__genres__[i])
            setattr(self, '_genre_names', gnames)
        return self._genre_names 

    def __repr__(self):
        return "Film(title=%r)" % self.title
    
    
class ClassRanking(Base):
    __tablename__ = 'class_rankings'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey(UserClass.id), index=True)
    film_id = Column(Integer, ForeignKey(Film.id), index=True)
    rate = Column(Float)
    
    def __init__(self, class_id, film_id, rate):
        self.class_id = class_id
        self.film_id = film_id
        self.rate = rate       

    def __repr__(self):
        rep = "Ranking(class_id={0}, film_id={1})"
        return rep.format(self.class_id, self.film_id)
    
    
class DBManager():
    __films_file__ = os.path.join(module_dir, 'db_data.csv')
    __sorting_file__ = os.path.join(module_dir, 'sorting_films.csv')
    
    def __init__(self):
        db_uri = "postgresql+psycopg2://{User}:{Password}@{Host}/{Database}"
        db_uri = db_uri.format(User=USER,Password=PASSWORD,Host=HOST,
                               Database=DATABASE)
        self.engine = sqlalchemy.create_engine(db_uri)
        
    def __create_tables__(self):
        confirm = input("Are you sure you want to create the tables? Y/N: ")
        if confirm == 'Y':
            Base.metadata.create_all(self.engine)
            self.fill_film_table()
            self.fill_genre_table()
            self.fill_user_class_table()
            self.fill_class_ranking_table()
        
    def __delete_tables__(self):
        confirm = input("Are you sure you want to delete the tables? Y/N: ")
        if confirm == 'Y':
            Base.metadata.drop_all(self.engine)
            
    def check_log_in_info(self, name, pwd):
        session = Session(self.engine)
        q = session.query(User).filter(User.name==name)
        qu = q.filter(User.pwd==pwd).first()
        result = 1 if qu else 0
        session.close()
        return result
    
    def fill_film_table(self):
        session = Session(self.engine)
        with open(self.__films_file__, 'r') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            genres = Genre.__genres__
            for film in reader:
                if film['rating']:
                    film['rating'] = float(film['rating'])
                else:
                    film['rating'] = None
                film['genres_id'] = [genres.index(c) + 1 for c in genres
                                     if int(film[c])]
                if film['runtime']:
                    film['runtime'] = int(film['runtime'])
                else:
                    film['runtime'] = 0
                if film['actors']:
                    acts = film['actors'].strip('[')
                    acts = acts.strip(']').split(',')
                    film['actors'] = [a.strip().strip("'").strip('"')
                                      for a in acts]
                else:
                    film['actors'] = []
                if film['directors']:
                    acts = film['directors'].strip('[')
                    acts = acts.strip(']').split(',')
                    film['directors'] = [a.strip().strip("'").strip('"')
                                         for a in acts]
                else:
                    film['actors'] = []
                if film['trailer']:
                    if film['trailer'].startswith('['):
                        trailer = film['trailer'].strip('[')
                        trailer = trailer.strip(']').split(',')
                        film['trailer'] = trailer[0]
                    film['trailer'] = film['trailer'].strip('[').strip(']')
                    film['trailer'] = film['trailer'].strip("'").strip('"')
                    if not film['trailer']:
                        film['trailer'] = None
                else:
                    film['trailer'] = None
                if film['netflix_id']:
                    if film['netflix_id'].startswith('['):
                        nid = film['netflix_id'].strip('[')
                        film['netflix_id'] = nid.strip(']').split(',')[0]
                    film['netflix_id'] = film['netflix_id'].strip('[')
                    film['netflix_id'] = film['netflix_id'].strip(']')
                    film['netflix_id'] = film['netflix_id'].strip("'")
                    film['netflix_id'] = film['netflix_id'].strip('"')
                    if not film['netflix_id']:
                        film['netflix_id'] = None
                else:
                    film['netflix_id'] = None
                film['descr'] = film['descr'][:499] if film['descr'] else None
                film_db = Film(**film)
                session.add(film_db)
        session.commit()
        session.close()
        
    def fill_genre_table(self):
        session = Session(self.engine)
        for i, gname in enumerate(Genre.__genres__):
            genre = Genre(gname)
            genre.id = i + 1
            session.add(genre)
        session.commit()
        session.close()
        
    def fill_user_class_table(self):
        session = Session(self.engine)
        for i in range(0, 4):
            user_class = UserClass('Default %s' % i)
            user_class.id = i
            session.add(user_class)
        session.commit()
        session.close()
        
    def fill_class_ranking_table(self):
        session = Session(self.engine)
        with open(self.__films_file__, 'r') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            films = {f['title']: f for f in reader}
            query = session.query(Film).filter(Film.title.in_(films.keys()))
            for f in query:
                film = films[f.title]
                rkg1 = ClassRanking(1, f.id, float(film['class1']))
                rkg2 = ClassRanking(2, f.id, float(film['class2']))
                rkg3 = ClassRanking(3, f.id, float(film['class3']))
                session.add_all([rkg1, rkg2, rkg3])
            session.commit()
            session.close()
            
    def query_films(self):
        session = Session(self.engine)
        return session, session.query(Film)
    
    def query_films_ratings(self, titles):
        session = Session(self.engine)
        q = session.query(ClassRanking.rate, Film.title, ClassRanking.class_id)
        q = q.filter(Film.id == ClassRanking.film_id)
        q = q.filter(Film.title.in_(titles))
        q = q.order_by(Film.title)
        return session, q
    
    def get_film_info(self, fid):
        session = Session(self.engine)
        f = session.query(Film).filter(Film.id == fid).first()
        keys = ['title', 'date', 'genre_names', 'descr', 'rating', 'poster', 
                'trailer', 'runtime', 'actors', 'directors']
        result = {k: str(getattr(f, k, '-')) for k in keys}
        return result
    
    def get_user_classes(self, people):
        session = Session(self.engine)
        names, pwds = zip(*people)
        q1 = session.query(User).filter(User.name.in_(names))
        q2 = session.query(UserClass.id)
        user_classes = {uc.id: 0. for uc in q2}
        for u in q1:
            for cid, v in u.class_ids:
                user_classes[cid] += v
        user_classes = {k: v / len(names) for k, v in user_classes.items()}
        return user_classes
    
    def get_people_film(self, people):
        session = Session(self.engine)
        names, pwds = zip(*people)
        q1 = session.query(User.unliked).filter(User.name.in_(names))
        d =  defaultdict(lambda: 0)
        for u in q1:
            for f in u.unliked:
                d[f] += 1
        q2 = session.query(User.pending).filter(User.name.in_(names))
        for u in q2:
            for f in u.pending:
                d[f] -= 1
        lflist, dflist = [], []
        for f, v in d.items():
            if v < 0:
                lflist.append(f)
            else:
                dflist.append(f)
        lfilms = session.query(Film).filter(Film.id.in_(lflist)).all()
        dfilms = session.query(Film).filter(Film.id.in_(dflist)).all()
        session.close()
        return lfilms, dfilms
        
    def add_user(self, name, pwd):
        session = Session(self.engine)
        user = User(name, pwd)
        try:
            with open(self.__sorting_file__, 'r') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                flist = [f['title'] for f in reader]
            sq = session.query(Film.title, Film.id, Film.poster)
            sq = sq.filter(Film.title.in_(flist)).order_by(func.random())
            session.add(user)
            session.commit()
            result = sq.all()[:10]
        except IntegrityError:
            result = None
        session.close()
        return result
    
    def update_user_class(self, name, pwd, rkgs):
        session = Session(self.engine)
        result = 0
        user = session.query(User).filter(User.name==name, User.pwd==pwd)
        if user.first():
            liked, unliked = [], []
            fids = [r[0] for r in rkgs]
            query = session.query(ClassRanking)
            query = query.filter(ClassRanking.film_id.in_(fids))
            db_rkgs = {(cr.film_id, cr.class_id): cr for cr in query}
            class1, class2, class3 = [1, 0.], [2, 0.], [3, 0.]
            for fid, rkg in rkgs:
                if rkg: liked.append(fid)
                else: unliked.append(fid)
                class1[1] += float(rkg) - db_rkgs[(fid, 1)].rate
                class2[1] += float(rkg) - db_rkgs[(fid, 2)].rate
                class3[1] += float(rkg) - db_rkgs[(fid, 3)].rate
            class1[1] = 1. - class1[1] / len(rkgs)
            class2[1] = 1. - class2[1] / len(rkgs)
            class3[1] = 1. - class3[1] / len(rkgs)
            class_ids = [class1, class2, class3]
            user.update({'class_ids': class_ids})
            user.update({'pending': liked})
            user.update({'liked': liked})
            user.update({'unliked': unliked})
            session.commit()
            result = 1
        session.close()
        return result
            
    def delete_user(self, name, pwd):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        query = query.filter(User.pwd==pwd)
        user = query.first()
        if user:
            if user.followers:
                q = session.query(User)
                flrs = q.filter(User.name.in_(user.followers))
                for u in flrs:
                    u.followings.remove(name)
                    qu = q.filter(User.name==u.name)
                    qu.update({'followings': u.followings})
            if user.followings:
                q = session.query(User)
                flgs = q.filter(User.name.in_(user.followings))
                for u in flgs:
                    u.followers.remove(name)
                    qu = q.filter(User.name==u.name)
                    qu.update({'followers': u.followers})
            session.delete(user)
            session.commit()
            result = 1
        session.close()
        return result
        
    def add_to_followings(self, uname, upwd, fname):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==uname)
        user = query.filter(User.pwd==upwd).first()
        if user:
            fquery = session.query(User).filter(User.name==fname)
            fuser = fquery.first()
            if fuser:
                fuser.followers.append(uname)
                fquery.update({'followers': fuser.followers})
                user.followings.append(fname)
                query.update({'followings': user.followings})
                session.commit()
                result = 1
        session.close()
        return result
                
    def delete_from_followings(self, uname, upwd, fname):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==uname)
        user = query.filter(User.pwd==upwd).first()
        if user:
            fquery = session.query(User).filter(User.name==fname)
            fuser = fquery.first()
            if fuser:
                fuser.followers.remove(uname)
                fquery.update({'followers': fuser.followers})
                user.followings.remove(fname)
                query.update({'followings': user.followings})
                session.commit()
                result = 1
        session.close()
        return result
    
    def add_to_pendings(self, name, pwd, fids):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user:
            for fid in fids:
                if fid not in user.liked:
                    user.liked.append(fid)
                if fid not in user.pending:
                    user.pending.append(fid)
                if fid in user.unliked:
                    user.unliked.remove(fid)
            query.update({'liked': user.liked})
            query.update({'pending': user.pending})
            query.update({'unliked': user.unliked})
            session.commit()
            result = 1
        session.close()
        return result
            
    def delete_from_pendings(self, name, pwd, ftitle):
        result = 0
        session = Session(self.engine)
        film = session.query(Film).filter(Film.title==ftitle).first()
        fid = film.id
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user and fid in user.pending:
            user.pending.remove(fid)
            query.update({'pending': user.pending})
            session.commit()
            result = 1
        session.close()
        return result
    
    def add_to_liked(self, name, pwd, film):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user:
            if film not in user.liked:
                user.liked.append(film)
                query.update({'liked': user.liked})
            if film in user.unliked:
                user.unliked.remove(film)
                query.update({'unliked': user.unliked})
            session.commit()
            result = 1
        session.close()
        return result
    
    def add_to_unliked(self, name, pwd, fids):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user:
            for fid in fids:
                if fid not in user.unliked:
                    user.unliked.append(fid)  
                    query.update({'unliked': user.unliked}) 
                if fid in user.liked:
                    user.liked.remove(fid)
                    query.update({'liked': user.liked})
                if fid in user.pending:
                    user.pending.remove(fid)
                    query.update({'pending': user.pending})   
            session.commit()
            result = 1
        session.close()
        return result
            
    def add_to_favorites(self, name, pwd, film):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user and film not in user.favorites:
            user.favorites.append(film)
            query.update({'favorites': user.favorites})
            session.commit()
            result = 1
        session.close()
        return result
            
    def delete_from_favorites(self, name, pwd, film):
        result = 0
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        if user and film in user.favorites:
            user.favorites.remove(film)
            query.update({'favorites': user.favorites})
            session.commit()
            result = 1
        session.close()
        return result
    
    def get_user(self, name, pwd):
        session = Session(self.engine)
        query = session.query(User).filter(User.name==name)
        user = query.filter(User.pwd==pwd).first()
        return user
    
    def check_user(self, name, pwd):
        user = self.get_user(name, pwd)
        session = Session(self.engine)
        if user and user.class_ids[0][0] == 0:
            with open(self.__sorting_file__, 'r') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                flist = [f['title'] for f in reader]
            sq = session.query(Film.title, Film.id, Film.poster)
            sq = sq.filter(Film.title.in_(flist)).order_by(func.random())
            result = sq.all()[:10]
        elif user and user.class_ids[0][0] > 0:
            result = 1
        else:
            result = None
        session.close()
        return result
    
    def get_pendings(self, name, pwd):
        session = Session(self.engine)
        pendings = session.query(User, Film)
        pendings = pendings.filter(User.pending.any(Film.id))
        pendings = pendings.filter(User.name==name).filter(User.pwd==pwd)
        return [p[1] for p in pendings]
