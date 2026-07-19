from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("analysis", "0002_live_connection_profiles")]

    operations = [
        migrations.AddField(
            model_name="analysisrun",
            name="locale",
            field=models.CharField(default="ru", max_length=8),
        ),
    ]
