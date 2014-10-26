__author__ = 'arshad'

from app.models import Channel, Node, Content, Profile

class ModelApi(object):

    def __init__(self, channel_name=None, facets=None, query=None, paged=False):
        if channel_name:
           channel = Channel.getByName(channel_name)
           model_class = Node.model_factory(channel.name)
        else:
            model_class = Content
        criteria = {'channels': channel_name}
        if facets:
            criteria['facets'] = facets

        if query is not None:
            if model_class == Profile:
                criteria['name'] = {'$regex': query}
            else:
                criteria['title'] = {'$regex': query}
        if model_class == Profile:
            self.option_display = 'name'
        else:
            self.option_display = 'title'
        if paged:
            self.models = model_class.objects(__raw__=criteria).all()[0:5]
        else:
            self.models = model_class.objects(__raw__=criteria).all()
        print [m.name for m in self.models]


    def dictify(self):
        models = [dict(option_value=str(u['id']), option_display=u[self.option_display], score=1) for u in self.models]
        return models