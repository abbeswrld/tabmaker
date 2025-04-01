from django.db import models
from . motion import Motion
from apps.profile.models import User
from apps.team.models import Team


# OG = Opening Government (Prime Minister & Deputy Prime Minister)
# OO = Opening Opposition (Leader of Opposition & Deputy Leader of Opposition)
# CG = Closing Government (Member of Government & Government Whip)
# CO = Closing Opposition (Member of Opposition & Opposition Whip)

class Game(models.Model):
    og = models.ForeignKey(Team, related_name='OG', on_delete=models.CASCADE)
    oo = models.ForeignKey(Team, related_name='OO', on_delete=models.CASCADE)
    cg = models.ForeignKey(Team, related_name='CG', on_delete=models.CASCADE)
    co = models.ForeignKey(Team, related_name='CO', on_delete=models.CASCADE)
    chair = models.ForeignKey(User, related_name='chair', on_delete=models.CASCADE)
    wing_left = models.ForeignKey(User, related_name='wing_left', blank=True, null=True, on_delete=models.CASCADE)
    wing_right = models.ForeignKey(User, related_name='wing_right', blank=True, null=True, on_delete=models.CASCADE)
    motion = models.ForeignKey(to=Motion, on_delete=models.CASCADE)
    date = models.DateTimeField()

    def get_teams(self) -> [Team]:
        return [self.og, self.oo, self.cg, self.co];


class GameResult(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE)

    # Position of speakers (true - if speakers were in the reverse order)
    og_rev = models.BooleanField(default=False)
    oo_rev = models.BooleanField(default=False)
    cg_rev = models.BooleanField(default=False)
    co_rev = models.BooleanField(default=False)

    @staticmethod
    def to_dict(team, place, s1, s2, rev):
        return {'team': team, 'place': place, 'speaker_1': s1, 'speaker_2': s2, 'revert': rev}
    
    def _is_fake_team(self, team):

        return team.is_fake if hasattr(team, 'is_fake') else False

    def _process_fake_result(self, team, result_data):
        if self._is_fake_team(team):
            if isinstance(result_data, int):
                return 0
            elif isinstance(result_data, bool):
                return False
        return result_data

    class Meta:
        abstract = True


class QualificationResult(GameResult):
    # Place
    og = models.IntegerField()
    oo = models.IntegerField()
    cg = models.IntegerField()
    co = models.IntegerField()

    # Speaker's points
    # OG (Prime Minister & Deputy Prime Minister)
    pm = models.IntegerField()
    pm_exist = models.BooleanField(default=True)
    dpm = models.IntegerField()
    dpm_exist = models.BooleanField(default=True)

    # OO (Leader of Opposition & Deputy Leader of Opposition)
    lo = models.IntegerField()
    lo_exist = models.BooleanField(default=True)
    dlo = models.IntegerField()
    dlo_exist = models.BooleanField(default=True)

    # CG (Member of Government & Government Whip)
    mg = models.IntegerField()
    mg_exist = models.BooleanField(default=True)
    gw = models.IntegerField()
    gw_exist = models.BooleanField(default=True)

    # CO (Member of Opposition & Opposition Whip)
    mo = models.IntegerField()
    mo_exist = models.BooleanField(default=True)
    ow = models.IntegerField()
    ow_exist = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        for position in ['og', 'oo', 'cg', 'co']:
            team = getattr(self.game, position)
            if self._is_fake_team(team):
                setattr(self, position, 0)
                if position == 'og':
                    self.pm = self.dpm = 0
                    self.pm_exist = self.dpm_exist = False
                elif position == 'oo':
                    self.lo = self.dlo = 0
                    self.lo_exist = self.dlo_exist = False
                elif position == 'cg':
                    self.mg = self.gw = 0
                    self.mg_exist = self.gw_exist = False
                elif position == 'co':
                    self.mo = self.ow = 0
                    self.mo_exist = self.ow_exist = False
        super().save(*args, **kwargs)


    def get_og_result(self):
        return self.to_dict(self.game.og, self.og, self.pm, self.dpm, self.og_rev)

    def get_oo_result(self):
        return self.to_dict(self.game.oo, self.oo, self.lo, self.dlo, self.oo_rev)

    def get_cg_result(self):
        return self.to_dict(self.game.cg, self.cg, self.mg, self.gw, self.cg_rev)

    def get_co_result(self):
        return self.to_dict(self.game.co, self.co, self.mo, self.ow, self.co_rev)


class PlayoffResult(GameResult):
    # Place
    og = models.BooleanField()
    oo = models.BooleanField()
    cg = models.BooleanField()
    co = models.BooleanField()

    def save(self, *args, **kwargs):
        for position in ['og', 'oo', 'cg', 'co']:
            team = getattr(self.game, position)
            if self._is_fake_team(team):
                setattr(self, position, False)
        super().save(*args, **kwargs)

    def get_og_result(self):
        return self.to_dict(self.game.og, self.og, 0, 0, self.og_rev)

    def get_oo_result(self):
        return self.to_dict(self.game.oo, self.oo, 0, 0, self.oo_rev)

    def get_cg_result(self):
        return self.to_dict(self.game.cg, self.cg, 0, 0, self.cg_rev)

    def get_co_result(self):
        return self.to_dict(self.game.co, self.co, 0, 0, self.co_rev)
