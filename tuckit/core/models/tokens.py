from django.db import models

from tuckit.core.models.org import Org


class ApiToken(models.Model):
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="tokens")
    name = models.CharField(max_length=200)
    token_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.org.slug})"


class OrgStatSnapshot(models.Model):
    """One row of org counts per calendar day, written lazily on Home
    load. Powers the Home summary cards' day-over-day deltas — no scheduler."""
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="stat_snapshots")
    date = models.DateField()
    building_ct = models.IntegerField(default=0)
    backlog_ct = models.IntegerField(default=0)
    shipped_week_ct = models.IntegerField(default=0)
    attention_ct = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "date"], name="uniq_org_snapshot_per_day"
            ),
        ]

    def __str__(self):
        return f"{self.org.slug} @ {self.date}"
