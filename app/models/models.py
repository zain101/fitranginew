import datetime, tempfile
import random, cStringIO
from PIL import Image as PImage
from flask import render_template
from mongoengine import Q
from app.handlers.messaging import send_single_email
from app.utils import convertLinks
from ago import human
from mongoengine import signals


def handler(event):

    def decorator(fn):
        def apply(cls):
            event.connect(fn, sender=cls)
            return cls

        fn.apply = apply
        return fn

    return decorator

@handler(signals.pre_save)
def update_content(sender, document):
    document.modified = datetime.datetime.now()
    if document.published and document.published_timestamp is None:
        document.published_timestamp = datetime.datetime.now()
    if isinstance(document, Profile):
        if document.title is None and document.name is not None:
            document.title = document.name
        update_slug(sender, document, 'profile')
    elif isinstance(document, Product):
        update_slug(sender, document, 'product')
    elif isinstance(document, Event):
        update_slug(sender, document, 'event')
    else:
        update_slug(sender, document, 'content')

def update_slug(sender, document, type):
    if document.slug is not None and len(document.slug) > 0:
        return
    original_slug = "/%s/%s" % (type, document.title.lower().replace(',', '-').replace('.', '-').replace(' ', '-'))
    _slug = original_slug
    count = 1
    while Content.objects(slug=_slug).first() is not None:
        _slug = original_slug + str(count)
        count += 1
    document.slug = _slug

class Configuration(object):

    @property
    def id(self):
        return self.name

    @classmethod
    def load_from_configuration(cls):
        from app.utils.general import get_channels, get_facets, get_roles
        data1 = get_facets()
        for d in data1:
            f = Facet(d['name'], d['parent'])
            print "Facet loaded", f.name, f.parent
            Facet.all_facets.append(f)

        data2 = get_channels()
        for d in data2:
            c = Channel(d['name'], d['type'], d['menu'], d['value'], d.get('template', None), d.get('menu_link', None), d.get('sub_menu', None))
            print "Channel loaded", c.name
            Channel.all_data.append(c)

        data3 = get_roles()
        for d in data3:
            r = Role(d['name'], d['value'])
            print "Role loaded", r.name
            Role.all_data_role.append(r)



class Facet(object):
    all_facets = []

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent

    def __repr__(self):
        return "%s [%s] " % (self.name, self.parent)

    @classmethod
    def get_facet_by_name(cls, _name):
        for f in Facet.all_facets:
            if f.name.lower() == _name.lower():
                return f
        return None

    @classmethod
    def find(cls, name):
        return cls.get_facet_by_name(name)

    @classmethod
    def get_facet_by_type(cls, _type):
        facets = []
        for f in Facet.all_facets:
            if f.type.lower() == _type.lower():
                facets.append(f)
        return facets

class Channel(object):
    all_data= []

    def __init__(self, name, parent, menu, display, template, menu_link, sub_menu=None):
        self.name = name
        self.parent = parent
        self.menu = menu
        self.display = display
        self.template = template
        self.menu_link = menu_link
        self.sub_menu = sub_menu

    def __repr__(self):
        return self.name

    @classmethod
    def get_all_names(cls):
        return  [c.name for c in Channel.all_data]

    @classmethod
    def getByName(cls, _name):
        for obj in cls.all_data:
            if obj.name != _name:
                continue
            return obj
        return None

    @classmethod
    def getByAlias(cls, alias):
        channel_name = None
        if alias == 'ACTIVITY':
            channel_name = 'Activity'
        elif alias == 'DESTINATION':
            channel_name = 'Destination'
        elif alias == 'ARTICLE':
            channel_name = 'Article'
        elif alias == 'ORGANISER':
            channel_name = 'Profile'
        elif alias == 'DEALER':
            channel_name = 'Profile'
        elif alias == 'Adventure Trip':
            channel_name = 'Adventure Trip'
        else:
            raise Exception("Invalid Alias")
        return cls.getByName(channel_name)

    def has_sub_type(self, subtype):
        for u in Channel.all_data:
            if self.name.lower().strip() == u.type.lower().strip():
                return True
        return False

    def getTypeByAlias(self, alias):
        if alias == 'ACTIVITY':
            channel_name = 'Activity'
        elif alias == 'DESTINATION':
            channel_name = 'Destination'
        elif alias == 'ARTICLE':
            channel_name = 'Article'
        elif alias == 'ORGANISER':
            channel_name = 'Organizer'
        elif alias == 'DEALER':
            channel_name = 'Gear Dealer'
        elif alias == 'Adventure Trip':
            channel_name = 'Adventure Trip'
        else:
            raise Exception("Invalid Alias")
        return channel_name

class Role(Configuration):

    all_data_role = []

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self): return self.value

class Node(object):

    def get_class_name(self):
        return self.__class__.__name__

    @classmethod
    def model_factory(cls, name):
        if name == 'Role':
            return Role
        elif name == 'Profile':
            return Profile
        elif name == 'Channel':
            return Channel
        elif name in ['Activity', 'Destination', 'Article', 'Content', 'Blog']:
            return Content 
        elif  name in ['Event', 'Adventure Trip']:
            return Event 
        elif name == 'Product':
            return Product
        elif name in ['Question', 'Forum']:
            return Question
        elif name in ['Post']:
            return Post
        elif name == 'Advertisement':
            return Advertisement
        else:
            raise Exception("Unknown type")

    def __unicode__(self):
        if getattr(self, 'name') is not None:
            return self.name
        else:
            return self.title

    @classmethod
    def channel_factory(cls, model):
        if cls == Advertisement:
            return 'Advertisement'
        for channel in Channel.all_data:
            if channel.name in set(model.channels):
                return channel.name
        raise Exception("Unset Channel for this model type %s %s" % (model.__class__.__name__, str(model)))


    def add_new(self, owner, **kwargs):
        self.set_values(True, **kwargs)
        self.created_timestamp = datetime.datetime.now()
        self.created_by = owner
        if self.__class__.__name__ == 'Question':
            mail_data = render_template('notifications/content_posted.html', user=owner, content=self)
            send_single_email("[Fitrangi] You have posted a question", to_list=[owner.email, 'admin@fitrangi.com'], data=mail_data)
        #self.published = True
        self.published_timestamp = datetime.datetime.now()
        self.save()
        return self

    def update_existing(self, **kwargs):
        self.set_values(False, **kwargs)
        self.save()
        return self

    def set_values(self, is_new, **kwargs):
        for k, v in kwargs.iteritems():
            if k.endswith('_ref'):
                if k and kwargs.has_key(k) and kwargs.get(k, False):
                    v = Content.get_by_id(v)
                    k = k.replace('_ref', '')
            if type(v) == str:
                v = v.strip()
            setattr(self, k, v)


    def upload_image(self, image):
        self.main_image = Image(image=image)
        self.save()
        return self


from app import db

class Image(db.EmbeddedDocument):
    image = db.ImageField(thumbnail_size=(100, 100, True))
    copyright = db.StringField()

class File(db. EmbeddedDocument):
    data = db.FileField()
    copyright = db.StringField()

class Comment(db.EmbeddedDocument):
    key = db.StringField()
    created_by = db.ReferenceField('Profile', required=True)
    created_on = db.DateTimeField(default=datetime.datetime.now, required=True)
    text = db.StringField()
    keywords = db.ListField(db.StringField())

    @property
    def since(self):
        return human(self.created_on, precision=1)

    @property
    def data(self):
        return convertLinks(self.text)

    def __unicode__(self): return "%s..." % self.text[0: 30 if len(self.text) > 10 else len(self.text)] 


@update_content.apply
class Content(Node, db.Document):
    __template__ = 'model/content/'
    __facets__ = ['Activity', 'Location']

    created_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    modified_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    created_by = db.ReferenceField('Profile')
    title = db.StringField()
    description = db.StringField()
    text = db.StringField()
    main_image = db.EmbeddedDocumentField(Image)
    additional_images = db.ListField(db.EmbeddedDocumentField(Image))
    attachments = db.ListField(db.EmbeddedDocumentField(File))
    slug = db.StringField()
    published = db.BooleanField(default=False)
    published_timestamp = db.DateTimeField(required=False)
    channels = db.ListField(db.StringField())
    facets = db.ListField(db.StringField())
    comments = db.ListField(db.EmbeddedDocumentField(Comment))
    parent = db.ReferenceField('Content', required=False)
    keywords = db.ListField(db.StringField())
    location = db.StringField()
    admin_published = db.BooleanField(default=False)
    youtube_embed = db.StringField()

    def visuals(self, small=False, url_only=False, detail=False):
        if not small and not url_only and self.youtube_embed is not None and len(self.youtube_embed) > 0:
            if detail:
                height = 'height="480px"'
            else:
                height = ''
            video = """
            <div class="col-sm-12 col-md-12">
                <center>
                    <iframe src="//www.youtube.com/embed/%s?controls=2" frameborder="0" allowfullscreen width="100%%" %s></iframe>
                </center>
            </div>
            """ % (str(self.youtube_embed), height)

            return video
        else:
            if not self.has_image:
                img_url = 'http://placehold.it/300x300&text=Fitrangi!'
            else:
                img_url = '/img/%s/%s' % (self.get_class_name(), str(self.id))
            if not small:
                sizing = ''
            else:
                sizing = 'height="30px" width="40px" class="img-circle"'
            if url_only:
                return img_url
            return '<img src="%s" class="img-responsive %s" alt="%s" %s/>' % (img_url, 'img-circle' if small else '', self.name if hasattr(self, 'name') and self.name is not None and len(self.name) > 0 else self.title, sizing)


    @property
    def since(self):
        return human(self.created_timestamp, precision=1)


    @property
    def data(self):
        return convertLinks(self.text)

    @classmethod
    def get_by_slug(cls, slug):
        return Content.objects(slug__iexact=slug).first()

    @classmethod
    def get_by_id(cls, id):
        content = Content.objects(pk=id).first()
        if content.slug is None or len(content.slug) is 0:
            if type(content) not in [Profile, Product, Event] and content.channels[0] not in Channel.get_all_names():
                return content
            update_slug(None, content, content.channels[0])
        return  content

    def get_image(self):
        if self and self.main_image:
            return self.main_image.image
        else:
            return None

    @property
    def has_image(self):
        if self and self.main_image and self.main_image.image:
            return True
        else:
            return False

    meta = {
        'allow_inheritance': True,
        'indexes': [
            {'fields': ['slug', 'title'], 'unique': False, 'sparse': False, 'types': False },
        ],
    }

    def __unicode__(self): return "%s..." % self.title

    @classmethod
    def addComment(cls, content_key, comment_text, author_key):
        author = Profile.objects(pk=author_key).first()
        content = Content.objects(pk=content_key).first()
        r = random.randint(1111111, 9999998999)
        comment = Comment(created_by=author, text=comment_text, key="%s-%d" % (str(content.id), r))
        content.comments.append(comment)
        content.modified_timestamp = datetime.datetime.now()
        content.save()
        return comment

class Answer(db.EmbeddedDocument):

    up_votes = db.IntField()
    down_votes = db.IntField()
    author = db.ReferenceField('Profile')
    answer = db.StringField()

@update_content.apply
class Question(Content):
    __template__ = 'model/forum/'
    answers = db.ListField(db.EmbeddedDocumentField(Answer))

    def __unicode__(self): return self.title

class Post(Content):
    __template__ = "model/post/"
    likes = db.ListField(db.ReferenceField('Profile'))
    dislikes = db.ListField(db.ReferenceField('Profile'))

@update_content.apply
class Profile(Content):
    __template__ = 'model/profile/'
    __facets__ = ['Profile']
    name = db.StringField()
    username = db.StringField()
    password = db.StringField()
    email = db.StringField()
    phone = db.StringField()
    address = db.StringField()
    is_social_login = db.BooleanField(default=False)
    following = db.ListField(db.ReferenceField('Profile'))
    follower = db.ListField(db.ReferenceField('Profile'))
    favorites = db.ListField(db.ReferenceField('Profile'))
    favorited_by = db.ListField(db.ReferenceField('Profile'))
    blogs = db.ListField(db.ReferenceField('Content'))
    questions = db.ListField(db.ReferenceField('Content'))
    answers = db.ListField(db.ReferenceField('Content'))
    is_verified = db.BooleanField('Verified')
    roles = db.ListField(db.StringField())
    facebook = db.StringField()
    linkedin = db.StringField()
    website = db.StringField()

    def __unicode__(self): return self.name

    @property
    def products(self, page=1, paginated=False):
        count = Product.objects(created_by=self).count()
        if not paginated:

            if count > 25:
                return Product.objects(created_by=self).order_by('-created_timestamp').all()[0: 25]
            else:
                return Product.objects(created_by=self).order_by('-created_timestamp').all()
        else:
            start =  (page - 1) * 25
            end = start + 25
            query = Product.objects(created_by=self)
            total = query.count()
            if start >= total - 1:
                return []
            if end >= total - 1:
                end = total
            return Product.objects(created_by=self).order_by('-created_timestamp').all()[start: end]


    @property
    def events(self, page=1, paginated=False):
        count = Event.objects(created_by=self).count()
        if not paginated:
            if count > 25:
                return Event.objects(created_by=self).order_by('-created_timestamp').all()[0: 25]
            else:
                return Event.objects(created_by=self).order_by('-created_timestamp').all()
        else:
            start =  (page - 1) * 25
            end = start + 25
            query = Event.objects(created_by=self)
            total = query.count()
            if start >= total - 1:
                return []
            if end >= total - 1:
                end = total
            return Event.objects(created_by=self).order_by('-created_timestamp').all()[start: end]

    def remove_from_favorites(self, another_profile):
        assert isinstance(another_profile, self.__class__)
        self.favorites.remove(another_profile)
        another_profile.favorited_by.remove(self)
        self.save()

    def add_to_favorites(self, another_profile):
        assert isinstance(another_profile, self.__class__)
        self.favorites.append(another_profile)
        self.save()
        another_profile.favorited_by.append(self)
        another_profile.save()
        mail_data = render_template('notifications/favorited.html', user=another_profile, adder=self)
        send_single_email("[Fitrangi] Someone just favorited you", to_list=[another_profile.email], data=mail_data)

    def unfollow(self, another_profile):
        assert isinstance(another_profile, self.__class__)
        self.following.remove(another_profile)
        another_profile.follower.remove(self)
        self.save()
        another_profile.save()

    def follow(self, another_profile):
        assert isinstance(another_profile, self.__class__)
        self.following.append(another_profile)
        mail_data = render_template('notifications/followed.html', user=another_profile, follower=self)
        send_single_email("[Fitrangi] Someone just followed you", to_list=[another_profile.email], data=mail_data)
        another_profile.follower.append(self)
        self.save()
        another_profile.save()

    def change_password(self, **kwargs):
        if kwargs['confirm'] == kwargs['password']:
            self.password = kwargs['password']
            self.save()
        else:
            raise Exception('Invalid Password, do not match')

    @classmethod
    def authenticate(cls, email, password):
        if password is None or len(password) is 0:
            return False
        profile = Profile.objects(Q(email__iexact=email) & Q(password__exact=password)).first()
        if profile and profile.email == email:
            return profile
        else:
            return False

    @classmethod
    def create_new(cls, name, email, password, is_verified=False, roles=['Enthusiast']):
        profile = Profile(name=name, email=email, password=password, is_verified=is_verified, roles=roles, facets=['Profile', 'Enthusiast'], channels=['Profile'])
        profile.save()
        return profile


EVENT_TYPES = ['Adventure Trip', 'Conclave', 'Exhibition', 'Conference', 'Meet up']

@update_content.apply
class Event(Content):
    __template__ = 'model/event/'
    __facets__ = ['Activity', 'Location', 'When', 'Amount']
    event_type = db.StringField(choices=EVENT_TYPES)
    start_date = db.StringField()
    end_date = db.StringField()
    duration = db.StringField()
    experiences = db.StringField()
    organiser = db.ReferenceField('Profile')
    amount = db.StringField()
    contact = db.StringField()
    location = db.StringField()
    source = db.StringField()
    destination = db.StringField()
    features = db.StringField()
    important_notes = db.StringField()
    links = db.StringField()



@update_content.apply
class Product(Content):
    __template__ = 'model/product/'
    price = db.FloatField()
    discount = db.FloatField(required=False)


class Tag(db.Document):

    name = db.StringField()

class Message(db.Document):
    __template__ = 'model/message/'

    created_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    created_by = db.ReferenceField('Profile')
    created_for = db.ReferenceField('Profile')
    message = db.StringField()

    @classmethod
    def get_by_id(cls, id):
        return Message.objects(pk=id).first()

    meta = {
        'allow_inheritance': True,
    }

    def __unicode__(self): return "%s..." % self.message

class UserMessage(Message): pass # Can be anonymous
class SubscriptionMessage(Message): pass # Can be anonymous
class Notification(Message): pass # Can be system generated


class AnalyticsEvent(db.Document):
    __template__ = 'model/message/'

    created_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    user = db.StringField()
    event_details = db.StringField()
    ip_address = db.StringField()
    url = db.StringField()

    @classmethod
    def get_by_id(cls, id):
        return AnalyticsEvent.objects(pk=id).first()

    meta = {
        'allow_inheritance': True,
    }

    def __unicode__(self): return "%s..." % self.message

class LoginEvent(AnalyticsEvent):
    pass

class VisitEvent(AnalyticsEvent):
    pass

PLACEMENTS = ['HOME TOP', 'HOME FOOTER', 'INTERNAL']
class Advertisement(db.Document, Node):
    __template__ = 'model/advertisement/'
    __FEATURED = 0
    __FEATURED_LONG = 1
    __NON_FEATURED_TOP = 2
    __NON_FEATURED_MIDDLE = 3
    __NON_FEATURED_BOTTOM = 4



    created_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    modified_timestamp = db.DateTimeField(default=datetime.datetime.now, required=True)
    created_by = db.ReferenceField('Profile')
    title = db.StringField()
    description = db.StringField()
    url = db.StringField()
    main_image = db.EmbeddedDocumentField(Image)
    long_image = db.EmbeddedDocumentField(Image)
    published = db.BooleanField()
    published_timestamp = db.DateTimeField(required=False)
    placements = db.ListField(db.StringField(choices=PLACEMENTS))

    def get_image(self, long=False):
        if self and self.main_image and not long:
            img = self.main_image
        elif self and self.long_image and long:
            img = self.long_image
        else:
            return None, None

        img_io = cStringIO.StringIO()
        img = PImage.open(img.image)
        format = self.main_image.image.format
        img.save(img_io, "JPEG", quality=70)
        img_io.seek(0)
        return img_io, format

    @classmethod
    def get_home_advertisements(cls):
        return list(Advertisement.objects(placements__in=['HOME TOP'], published__exact=True).all()[0: 2])

    @classmethod
    def get_home_footer_advertisement(cls):
        total = Advertisement.objects(placements__in=['HOME FOOTER'], published__exact=True).count()
        if total is 0:
            return None
        if total > 1:
            r = random.randint(0, total - 1)
        else:
            r = 0
        print total, r
        return Advertisement.objects(placements__in=['HOME FOOTER'], published__exact=True).all()[r]

    @classmethod
    def get_internal_advertisements(cls):
        return list(Advertisement.objects(placements__in=['INTERNAL'], published__exact=True).all()[0: 6])





Configuration.load_from_configuration()

if __name__ == '__main__':
    print 'Test Models'
