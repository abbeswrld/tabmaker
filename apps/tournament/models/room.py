from django.db import models
from . game import Game
from apps.place.models import Place
from apps.round.models import Round


class Room(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, blank=True, null=True, on_delete=models.SET_NULL)
    number = models.IntegerField(blank=True)

