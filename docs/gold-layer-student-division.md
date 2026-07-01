# Gold Layer - Podela rada

## Cilj gold sloja

Gold layer je zavrsni analiticki sloj projekta.

Bronze sloj cuva sirove podatke.

Silver sloj cisti i normalizuje podatke u zajednicki model.

Gold sloj koristi silver podatke i pravi tabele koje su spremne za analizu, dashboard i izvestaje.

Gold sloj ne treba da bude kopija silver sloja. On treba da odgovori na konkretna pitanja:

- koliko aktivnosti ima po danu;
- koji postovi imaju najveci engagement;
- koji korisnici su najaktivniji;
- koji tagovi ili teme su najzastupljeniji;
- kakav je kvalitet podataka po platformi.

## Model podele

Gold layer se deli isto kao silver layer.

```text
Silver:
Student 1 = infrastruktura
Student 2 = Hacker News normalizacija
Student 3 = X normalizacija

Gold:
Student 1 = infrastruktura
Student 2 = Hacker News agregacije
Student 3 = X agregacije
```

Ovim se zadrzava jasna odgovornost:

- Student 1 pravi AWS/CDK osnovu.
- Student 2 radi poslovnu logiku za Hacker News.
- Student 3 radi poslovnu logiku za X.

## Student 1 - Gold infrastruktura

Student 1 je zaduzen za infrastrukturu gold sloja.

Obaveze:

- dodati novi CDK stack: `GoldStack`;
- povezati `GoldStack` sa postojecim `DataLakeStack`;
- dodati Lambda resource-e za gold obradu;
- dodati IAM role po principu least privilege;
- omoguciti gold Lambda funkcijama citanje iz `silver/*`;
- omoguciti gold Lambda funkcijama pisanje u `gold/*`;
- omoguciti CloudWatch logove;
- dodati environment variables kao stabilan ugovor za tim;
- dodati CloudFormation output-e za imena gold Lambda funkcija;
- dodati CDK assertion testove;
- dodati dokumentaciju za deploy i manual invoke.

Predlozeni resource-i:

```text
GoldStack
build-hn-gold Lambda
build-x-gold Lambda
```

Minimalna IAM prava:

```text
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
s3:ListBucket za prefikse silver/* i gold/*
s3:GetObject nad silver/*
s3:PutObject nad gold/*
```

Environment variables:

```text
DATA_LAKE_BUCKET
SILVER_PREFIX=silver
GOLD_PREFIX=gold
HN_GOLD_PREFIX=gold/hacker-news
X_GOLD_PREFIX=gold/x
```

Gold Lambda handleri sada rade prave agregacije nad silver Parquet datasetima.
Posto su `silver/users`, `silver/posts`, `silver/post_tags` i
`silver/data_quality_report` zajednicki folderi za obe platforme, gold citanje
mora koristiti platform partition filter:

```text
build-hn-gold cita samo platform=HackerNews
build-x-gold cita samo platform=X
```

Ovo sprecava spajanje HN i X Parquet sema pre filtriranja.

Definition of done za Student 1:

- `GoldStack` postoji u CDK aplikaciji;
- postoje gold Lambda resource-i;
- IAM policy dozvoljava citanje `silver/*` i pisanje `gold/*`;
- nema admin/wildcard pristupa van potrebnog opsega;
- env var ugovor je dokumentovan;
- CDK testovi prolaze;
- `cdk synth` prolazi;
- postoji deploy dokumentacija;
- HN i X gold runtime invoke vracaju `status=success`;
- S3 sadrzi Parquet fajlove pod `gold/hacker-news/` i `gold/x/`.

## Student 2 - Hacker News gold

Student 2 je zaduzen za Hacker News gold agregacije.

Preuslov:

- Hacker News silver mora da proizvede normalizovane tabele u `silver/`.

Ulaz:

```text
silver/users/
silver/posts/
silver/post_tags/
silver/post_relations/
silver/data_quality_report/
```

Izlaz:

```text
gold/hacker-news/daily_item_counts/
gold/hacker-news/daily_users_metric/
gold/hacker-news/top_story_posts/
gold/hacker-news/top_job_posts/
gold/hacker-news/top_users_by_karma/
gold/hacker-news/bottom_users_by_karma/
gold/hacker-news/data_quality_summary/
```

Predlozene metrike:

- distribucija tipova objava: story, ask, job, poll, comment;
- broj Hacker News korisnika po danu;
- top 10 story objava po score vrednosti;
- top 10 job objava po score vrednosti;
- top 10 korisnika sa najvecim karma_score;
- top 10 korisnika sa najmanjim karma_score;
- data quality summary za Hacker News.

Definition of done za Student 2:

- HN gold Lambda cita HN silver podatke;
- HN gold Lambda pravi agregirane rezultate;
- rezultati se upisuju u `gold/hacker-news/`;
- output je pogodan za analitiku, idealno Parquet dataset;
- postoje testovi za transformacionu logiku.

## Student 3 - X gold

Student 3 je zaduzen za X gold agregacije.

Preuslov:

- X silver mora da proizvede normalizovane tabele u `silver/`.

Ulaz:

```text
silver/users/
silver/posts/
silver/post_tags/
silver/post_relations/
silver/data_quality_report/
```

Izlaz:

```text
gold/x/daily_users_metric/
gold/x/top_users_by_followers/
gold/x/top_posts_by_engagement/
gold/x/hashtag_trends/
gold/x/data_quality_summary/
```

Predlozene metrike:

- broj X korisnika po danu;
- top 10 X korisnika po followers_count;
- top postovi po engagement score-u;
- top hashtagovi po danu;
- engagement score po postu;
- data quality summary za X.

Definition of done za Student 3:

- X gold Lambda cita X silver podatke;
- X gold Lambda pravi agregirane rezultate;
- rezultati se upisuju u `gold/x/`;
- output je pogodan za analitiku, idealno Parquet dataset;
- postoje testovi za transformacionu logiku.

## Zajednicki ugovor

Gold layer cita samo iz silver sloja:

```text
silver/*
```

Gold layer pise samo u gold sloj:

```text
gold/*
```

Konvencija za S3 putanje:

```text
gold/hacker-news/<table_name>/
gold/x/<table_name>/
```

Predlozene gold tabele:

```text
daily_item_counts
daily_users_metric
top_story_posts
top_job_posts
top_users_by_karma
bottom_users_by_karma
top_users_by_followers
top_posts_by_engagement
hashtag_trends
data_quality_summary
```

## Redosled rada

1. Student 1 pravi `GoldStack`, IAM, Lambda scaffold, docs i testove.
2. Student 2 zavrsava HN silver ako jos nije gotov.
3. Student 3 zavrsava/proverava X silver ako jos nije gotov.
4. Student 2 implementira HN gold agregacije.
5. Student 3 implementira X gold agregacije.
6. Tim zajedno proverava outpute u S3 i priprema dokaz za odbranu.

## Test plan

Student 1:

- `python -m pytest -q`;
- `cdk synth`;
- provera da `GoldStack` postoji;
- provera da postoje gold Lambda funkcije;
- provera IAM policy-ja;
- provera env var ugovora.

Student 2:

- unit testovi za HN agregacije;
- manual invoke `build-hn-gold`;
- provera fajlova u `gold/hacker-news/`.

Student 3:

- unit testovi za X agregacije;
- manual invoke `build-x-gold`;
- provera fajlova u `gold/x/`.

## Napomena

Student 1 deo moze biti zavrsen nezavisno od Student 2 i Student 3 logike.

To znaci da infrastruktura moze biti spremna pre nego sto realni gold podaci postoje.

U tom stanju je ispravno reci:

```text
Gold infrastructure is ready.
Business aggregation depends on completed silver outputs and Student 2/3 gold logic.
```
