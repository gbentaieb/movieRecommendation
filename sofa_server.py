#==============================================================================
# Imports and Global Variables
#==============================================================================

import threading
import datetime as dt
from twisted.internet.protocol import Factory, Protocol
from twisted.internet import reactor
from collections import defaultdict

from sofa.sofa_reco import Recommender
from sofa.sofa_db import DBManager, Genre

#==============================================================================
# Main classes
#==============================================================================

class AppFilm():
    """Base class for Movies."""
    def __init__(self, title, poster, id=None):
        self.title = str(title)
        self.poster = str(poster)
        self.id = id
        self.nb_rating = 0
        self.rating = 0
        
    def add_rating(self, rating):
        self.rating += rating
        self.nb_rating += 1
        

class Sofa():
    """Base class for Sofas."""
    genres = Genre.__genres__
    
    def __init__(self, name):
        self._name = name
        self._people = set()
        self.waiting_clients = []
        self.last_update = dt.datetime.now()
        self.preferences = {c:[] for c in self.genres}
        
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, new_name):
        self._name = new_name
        self.last_update = dt.datetime.now()
        
    @property
    def nb_people(self):
        return len(self._people)
    
    @property
    def people(self):
        return self._people
    
    @people.setter
    def people(self, new_set):
        self._people = new_set
        self.last_update = dt.datetime.now()       
        
        
class SofaManager():
    """Class to manage the existing Sofas."""
    genres = Genre.__genres__  
    class Duplicate(Exception):
        """To be raised when a Sofa already exists."""
        pass

    def __init__(self):
        self.recommender = Recommender()
        self.sofas = defaultdict(lambda: None)
        self.first_recommandation = defaultdict(lambda: None)
        self.final_recommandation = defaultdict(lambda: None)
        self.ctrl_thread = False
        
    def __enter__(self):
        self.start_ctrl_thread()
        
    def __exit__(self, type, value, tb):
        self.stop_ctrl_thread()
        
    def start_ctrl_thread(self, step=300, max_age=600):
        self.ctrl_thread = True
        def ctrl_thread():
            if self.ctrl_thread:
                for sname, sofa in list(self.sofas.items()):
                    if sofa:
                        age = dt.datetime.now() - sofa.last_update
                        if age.seconds > max_age:
                            self.delete_sofa(sname)
                    else:
                        self.delete_sofa(sname)
                timer = threading.Timer(step, ctrl_thread)
                timer.start()
        ctrl_thread()
                
    def stop_ctrl_thread(self):
        self.ctrl_thread = False
        
    def new_sofa(self, sname):
        if self.sofas[sname]:
            raise self.Duplicate('The sofa %s already exists' % sname)
        else:
            self.sofas[sname] = Sofa(sname)
            
    def add_preferences(self, uname, pwd, sname, pref_list):
        for c, p in zip(self.genres, pref_list):
            self.sofas[sname].preferences[c].append(int(p))
        s = self.sofas[sname].people
        s.add((uname, pwd))
        self.sofas[sname].people = s 
        
    def get_nb_people(self, sname):
        return self.sofas[sname].nb_people
    
    def recommend(self, sname):
        sofa = self.sofas[sname]
        ratings = zip(*[sofa.preferences[c] for c in self.genres])
        films = [AppFilm(f[0], f[1], f[2])
                 for f in self.recommender.recommend(ratings, sofa.people)]
        return films
     
    def send_first_recommandation(self, sname):
        self.first_recommandation[sname] = films = self.recommend(sname)
        for client in self.sofas[sname].waiting_clients:
            posters = ';'.join([f.poster for f in films])
            ids = ';'.join([str(f.id) for f in films])
            client.write('::'.join([posters, ids]))
        self.sofas[sname].waiting_clients = []

    def add_films_rating(self, sname, rating_list):
        for f, r in zip(self.first_recommandation[sname], rating_list):
            f.add_rating(r)
        self.sofas[sname].last_update = dt.datetime.now()

    def get_final_recommandation(self, sname, client):
        nb_people = self.sofas[sname].nb_people
        self.sofas[sname].waiting_clients.append(client)
        if self.first_recommandation[sname][0].nb_rating >= nb_people:
            result = self.first_recommandation[sname][0]
            for f in self.first_recommandation[sname][1:]:
                if f.rating > result.rating:
                    result = f
            self.final_recommandation[sname] = result
            for client in self.sofas[sname].waiting_clients:
                client.write(str(result.id) + ';' + result.poster)
            self.sofas[sname].waiting_clients = []
    
    def delete_sofa(self, sname):
        try: self.sofas.pop(sname)
        except KeyError: pass
        try: self.first_recommandation.pop(sname)
        except KeyError: pass
        try: self.final_recommandation.pop(sname)
        except KeyError: pass       
        
class ServerProtocol(Protocol):
    """A server Class. Deals with the messages received from users."""
    
    @classmethod
    def launch(cls):
        cls.sofa_manager = SofaManager()
        cls.db_manager = DBManager()
        with cls.sofa_manager:
            factory = Factory()
            factory.protocol = cls
            reactor.listenTCP(80, factory)
            print("Server started listening.")
            reactor.run()
        
    def connectionMade(self):
        print("a client connected")

    def dataReceived(self, data):
        print('data received: ' + data)
        try:
            reply = self.reply(data)
            if reply:
                print('data sent: ' + reply)
                self.transport.write(str(reply))
        except Exception as e:
            self.transport.write('NULL')
            msg = 'Bad data sent. Error generated: (%s) ' % str(type(e))
            print(msg + str(e))
    
    def reply(self, rdata):
        data = rdata.strip(';').split(';')
        request, name = int(data[0]), data[1]
        
        # Recommendation        
        if request == 10:
            try: 
                self.sofa_manager.new_sofa(name)
                return '1'
            except SofaManager.Duplicate: 
                return '0'
        elif request == 11:
            return '1' if self.sofa_manager.sofas[name] else '0'
        elif request == 2:
            self.sofa_manager.add_preferences(name, data[2], data[3], data[4:])
            return '1'
        elif request == 3:
            return str(self.sofa_manager.sofas[name].nb_people)
        elif request == 40:
            client = self.transport
            self.sofa_manager.sofas[name].waiting_clients.append(client)
            self.sofa_manager.send_first_recommandation(name)
            print('First recommendation sent!')
        elif request == 41:
            client = self.transport
            self.sofa_manager.sofas[name].waiting_clients.append(client)
        elif request == 5:
            rating = [int(d) for d in data[2:]]
            self.sofa_manager.add_films_rating(name, rating)
            return '1'
        elif request == 6:
            self.sofa_manager.get_final_recommandation(name, self.transport)
            print('Final recommendation sent!')
        elif request == 7:
            self.sofa_manager.delete_sofa(name)
        
        #DB modification
        elif request == 8:
            pwd = data[2]
            return str(self.db_manager.check_log_in_info(name, pwd))
        elif request == 90:
            pwd, status = data[2:]
            if status == '1':
                result = self.db_manager.check_user(name, pwd)
            elif status == '0':
                result = self.db_manager.add_user(name, pwd)
            if result is None:
                return '0::-'
            elif result == 1:
                return '1::-'
            else:
                res = ';'.join([str(r.id) for r in result])
                res += '::' + ';'.join([r.poster for r in result])
                res = '1::' + res 
                return res 
        elif request == 91:
            pwd = data[2]
            return str(self.db_manager.delete_user(name, pwd))
        elif request == 92:
            pwd, ids, choices = data[2:]
            ids, choices = ids.split('::'), choices.split('::')
            ids, choices = [int(i) for i in ids], [int(c) for c in choices]
            rkgs = zip(ids, choices)
            return str(self.db_manager.update_user_class(name, pwd, rkgs))
        elif request == 100:
            pwd, fname = data[2:]
            return str(self.db_manager.add_to_followings(name, pwd, fname))
        elif request == 110:
            pwd, fname = data[2:]
            r = self.db_manager.delete_from_followings(name, pwd, fname)
            return str(r)
        elif request == 120:
            pwd, status, films = data[2:]
            status = [int(s) for s in status.split('::')]
            films = films.split('::')
            pdg = [films[i] for i, s in enumerate(status) if s==1]
            ulkd = [films[i] for i, s in enumerate(status) if s==0]
            res = self.db_manager.add_to_pendings(name, pwd, pdg)
            res = str(res * self.db_manager.add_to_unliked(name, pwd, ulkd))
            return res
        elif request == 130:
            pwd, film = data[2:]
            r = self.db_manager.delete_from_pendings(name, pwd, film)
            return str(r)
        elif request == 140:
            pwd, film = data[2:]
            return str(self.db_manager.add_to_favorites(name, pwd, film))
        elif request == 150:
            pwd, film = data[2:]
            r = self.db_manager.delete_from_favorites(name, pwd, film)
            return str(r)
        elif request == 160:
            pwd, start_idx, end_idx = data[2], int(data[3]), int(data[4])
            films = self.db_manager.get_pendings(name, pwd)[start_idx:end_idx]
            films = [(f.id, f.title, f.poster, f.netflix_id, f.rating)
                     for f in films]
            result = [';'.join([str(a) for a in f]) for f in films]
            result = ['(%s)' % r for r in result]
            return '160::[%s]' % '-'.join(r for r in result)
        elif request == 170:
            fid = name
            result = self.db_manager.get_film_info(fid)
            descr = result.pop('descr')
            res = ';'.join('::'.join([k, v]) for k, v in result.items())
            return res + ';descr::' + descr
            
            