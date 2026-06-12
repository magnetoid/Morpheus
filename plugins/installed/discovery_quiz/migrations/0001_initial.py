from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=80, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('intro', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('text', models.CharField(max_length=400)),
                ('qtype', models.CharField(choices=[('single', 'Single choice'), ('multi', 'Multi choice'), ('text', 'Text input')], default='single', max_length=10)),
                ('mapping_json', models.TextField(blank=True, default='{}')),
                ('quiz', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='questions', to='discovery_quiz.quiz')),
            ],
            options={'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='Option',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('key', models.SlugField(max_length=60)),
                ('label', models.CharField(max_length=200)),
                ('order', models.PositiveIntegerField(default=0)),
                ('question', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='options', to='discovery_quiz.question')),
            ],
            options={'ordering': ['order']},
        ),
        migrations.AlterUniqueTogether(
            name='option',
            unique_together={('question', 'key')},
        ),
        migrations.CreateModel(
            name='QuizResultTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('category_slug', models.SlugField(max_length=80)),
                ('intro', models.TextField(blank=True)),
                ('cta_label', models.CharField(blank=True, max_length=80)),
                ('quiz', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='result_templates', to='discovery_quiz.quiz')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='quizresulttemplate',
            unique_together={('quiz', 'category_slug')},
        ),
        migrations.CreateModel(
            name='QuizSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('answers_json', models.TextField(default='{}')),
                ('result_category', models.SlugField(blank=True, max_length=80)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='auth.user')),
                ('quiz', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='submissions', to='discovery_quiz.quiz')),
            ],
            options={'ordering': ['-submitted_at']},
        ),
        migrations.AddIndex(
            model_name='quizsubmission',
            index=models.Index(fields=['quiz', '-submitted_at'], name='discovery_q_quiz_2b8c01_idx'),
        ),
    ]
