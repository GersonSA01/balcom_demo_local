# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0010_balconagente_balconprocesoservicio_balconrequisito_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='businessprocess',
            old_name='business_context',
            new_name='descripcion',
        ),
        migrations.AlterField(
            model_name='businessprocess',
            name='descripcion',
            field=models.TextField(blank=True, null=True, verbose_name='Descripción'),
        ),
        migrations.AlterField(
            model_name='businessprocess',
            name='nombre',
            field=models.CharField(max_length=500, verbose_name='Nombre del Proceso'),
        ),
    ]






