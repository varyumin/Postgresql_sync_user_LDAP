![Alt text](https://cdn.auth0.com/docs/media/connections/windows.png)
![Alt text](http://cdn.mysitemyway.com/etc-mysitemyway/icons/legacy-previews/icons-256/black-white-pearls-icons-alphanumeric/069302-black-white-pearl-icon-alphanumeric-plus-sign.png)
![Alt text](https://javalec.files.wordpress.com/2014/12/postgresql-logo.png)

# Сompatibility

### Python 2.7 and 3.x

# Install

##### git clone https://bitbucket.sberned.ru/scm/~varyumin/sync-user-from-ldap-to-postgresql.git

##### pip install -r requirements.txt

# Configurate

## Example
```
config:
  LDAP_server:
    server: '10.210.17.116'     # IP для подключения к Active Directory
    port: 636                   # Порт подключения к Active Directory
    user: VARyumin@sberned      # Пользователь от которого будут покдючатся к Active Directory
    password: P@SSword          # Пароль от которого будут покдючатся к Active Directory
    base_DN: DC=sberned,DC=lc   #

  DB_sever:
    server: '10.210.17.135'     # IP PostgreSQL
    port: '5432'                # Port PostgreSQL
    db_name: 'postgres'         # Database PostgreSQL
    user: 'postgres'            # User Administrator PostgreSQL
    password: 'PoStGrEsQL'      # Password Administrator PostgreSQL
    tech_user:                  # Технические учетки. По ним никаких изменений и правил не будут применяться
      - postgres
      - sgr
      - css

  Mapping:                      # Тут перечисляются РОЛИ. С какой группой в AD смапить. Какие гранты у этой роли.
    read:                       # И флаг default в какую по умолчанию добавлять новых пользователей
      group_bind: 'CN=read.prod.sgr,OU=PostgreSQL,OU=Linux Server,DC=sberned,DC=lc'
      grant:
        - SELECT
      default: True
    write:
      group_bind: 'CN=write.prod.sgr,OU=PostgreSQL,OU=Linux Server,DC=sberned,DC=lc'
      grant:
        - SELECT
        - INSERT
        - UPDATE
        - DELETE
```

# Run test and Add to cron

```
usage: sync_to_ad.py [-h] [-f FILE] [-r RUN]

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Specify the configuration file. If you do not specify,
                        the default file will be used ./config.yml
  -r RUN, --run RUN     sync or analyz(DEFAULT). sync: WARNING! Will be
                        synchronized users with Active Directory analyz:
                        Analyzes user but NO CHANGES it produces!
```
## Сперва запускаем с флагом analyz и смотрим какие изменения произойдут

```
sync_to_ad.py --run analyz
{'add': ['esgolovachev'], 'del': ['aanosova', 'haydarov']}
```
## Если нас все устраивает добавляем в крон с флагом  sync

```
*/30 * * * * cd /home/varyumin/sync-user-from-ldap-to-postgresql && ./sync_to_ad.py --run sync
```

## Логи синхронизации /var/log/sync_pgsql_to_ad.log
```
[2017-09-07 15:48:22,253] 	sync_to_ad.py[LINE:121]# INFO     		Role "read" in PostgreSQL find
[2017-09-07 15:48:22,256] 	sync_to_ad.py[LINE:129]# DEBUG    		GRANT CONNECT ON DATABASE prod_sgr TO read;
[2017-09-07 15:48:22,256] 	sync_to_ad.py[LINE:133]# DEBUG    		GRANT USAGE ON SCHEMA public TO read;
[2017-09-07 15:48:22,257] 	sync_to_ad.py[LINE:137]# DEBUG    		GRANT SELECT ON ALL TABLES IN SCHEMA public TO read;
[2017-09-07 15:48:22,264] 	sync_to_ad.py[LINE:129]# DEBUG    		GRANT CONNECT ON DATABASE testdb TO read;
[2017-09-07 15:48:22,266] 	sync_to_ad.py[LINE:121]# INFO     		Role "write" in PostgreSQL find
[2017-09-07 15:48:22,268] 	sync_to_ad.py[LINE:129]# DEBUG    		GRANT CONNECT ON DATABASE prod_sgr TO write;
[2017-09-07 15:48:22,269] 	sync_to_ad.py[LINE:133]# DEBUG    		GRANT USAGE ON SCHEMA public TO write;
[2017-09-07 15:48:22,270] 	sync_to_ad.py[LINE:137]# DEBUG    		GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO write;
[2017-09-07 15:48:22,275] 	sync_to_ad.py[LINE:129]# DEBUG    		GRANT CONNECT ON DATABASE testdb TO write;
[2017-09-07 15:48:22,288] 	sync_to_ad.py[LINE:152]# INFO     		DELETE User: []
[2017-09-07 15:48:22,288] 	sync_to_ad.py[LINE:153]# INFO     		ADD User: ['esgolovachev']
[2017-09-07 15:48:22,289] 	sync_to_ad.py[LINE:164]# DEBUG    		CREATE USER "esgolovachev" IN ROLE "read"
```
