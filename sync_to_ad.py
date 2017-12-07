#!/usr/bin/env python

from ldap3 import Server, Connection, ALL
import yaml
import psycopg2
import logging
import traceback
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', default="config.yml",
                    help='Specify the configuration file. If you do not specify, the default file will be used ./config.yml')
parser.add_argument('-r', '--run', default="analyz",
                    help='sync or analyz(DEFAULT). sync: WARNING! Will be synchronized users with Active Directory analyz: Analyzes user but NO CHANGES it produces!')
args = vars(parser.parse_args())
logging.basicConfig(format=u'[%(asctime)s] \t%(filename)s[LINE:%(lineno)d]# %(levelname)-8s \t\t%(message)s',
                    level=logging.DEBUG, filename=u'/var/log/sync_pgsql_to_ad.log')

try:
    conf = yaml.load(open(args['file']))['config']
    ldap = conf['LDAP_server']
    db = conf['DB_sever']
    tech_users = db['tech_user']
    mapping = conf['Mapping']

    def GetDefaultRole():
        for role, value in mapping.items():
            if value.get('default'):
                def_role = role
                break
            else:
                def_role = 'read'
        return def_role


    def GetRoles():
        roles = []
        for role, value in mapping.items():
            roles.append(role)
        return roles


    def GroupLdapBind():
        groups = []
        for role, value in mapping.items():
            groups.append(value['group_bind'])
        return groups


    server = Server(ldap['server'], port=ldap['port'], get_info=ALL, use_ssl=True)
    conn = Connection(server, user=ldap['user'], password=ldap['password'], auto_bind=True)

    conn_db = psycopg2.connect(
        "host='{}' port='{}' dbname='{}' user='{}' password='{}'".format(db['server'], db['port'], db['db_name'],
                                                                         db['user'], db['password']))


    def SearchUserAdGroup(args):
        user_from_ad_to_pgsql = {}
        for memberOf in args:
            conn.search(search_base=ldap['base_DN'], search_filter='(memberOf={})'.format(memberOf),
                        attributes=('sAMAccountName'))
            for key, value in mapping.items():
                if value['group_bind'] == memberOf:
                    user_from_ad_to_pgsql[key] = []
                    for user in conn.entries:
                        user_from_ad_to_pgsql[key].append(str(user['sAMAccountName']).lower())
        return user_from_ad_to_pgsql


    def GetAllUserPgsql():
        pg_user = []
        sql = "SELECT usename FROM pg_user;"
        cur = conn_db.cursor()
        cur.execute(sql)
        for user in cur.fetchall():
            pg_user.append(user[0])
        cur.close()
        print(pg_user)
        return pg_user


    def GetAllBaseAndSchem():
        all_base = {}
        dbs_sql = "SELECT datname FROM pg_database WHERE datname NOT IN ('postgres', 'template0', 'template1');"
        cur = conn_db.cursor()
        cur.execute(dbs_sql)
        for database in cur.fetchall():
            schems_list = []
            conn_db_name = psycopg2.connect(
                "host='{}' port='{}' dbname='{}' user='{}' password='{}'".format(db['server'],
                                                                                 db['port'],
                                                                                 database[0],
                                                                                 db['user'],
                                                                                 db['password']))

            schems_sql = "SELECT schemaname FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') GROUP BY schemaname;"
            cur_name = conn_db_name.cursor()
            cur_name.execute(schems_sql)
            for schem in cur_name.fetchall():
                if schem[0]:
                    schems_list.append(schem[0])
            all_base[database[0]] = schems_list
            cur_name.close()
            conn_db_name.close()
        cur.close()
        return all_base


    def ChekOrAdd(args, dbs, run='sync'):
        for role in args:
            sql = "SELECT rolname FROM pg_roles WHERE rolname = '{}';".format(role)
            cur = conn_db.cursor()
            cur.execute(sql)
            if not cur.fetchall():
                cur = conn_db.cursor()
                cur.execute("CREATE USER {} NOLOGIN;".format(role))
                conn_db.commit()
                logging.info(u'Role \"{}\" no found. Create \"{}\" '.format(role, role))
                logging.debug(u"CREATE USER {} NOLOGIN;".format(role))

            else:
                logging.info(u'Role \"{}\" in PostgreSQL find'.format(role))
            for db_name, schems in dbs.items():
                conn_db_temp = psycopg2.connect(
                    "host='{}' port='{}' dbname='{}' user='{}' password='{}'".format(db['server'], db['port'],
                                                                                     db_name,
                                                                                     db['user'], db['password']))
                cur_tmp = conn_db_temp.cursor()
                cur_tmp.execute("GRANT CONNECT ON DATABASE {} TO {};".format(db_name, role))
                logging.debug(u"GRANT CONNECT ON DATABASE {} TO {};".format(db_name, role))
                if schems:
                    for schem in schems:
                        cur_tmp.execute("GRANT USAGE ON SCHEMA {} TO {};".format(schem, role))
                        logging.debug(u"GRANT USAGE ON SCHEMA {} TO {};".format(schem, role))
                        cur_tmp.execute("GRANT {} ON ALL TABLES IN SCHEMA {} TO {};".format(
                            ', '.join(map(str, mapping[role]['grant'])), schem, role))
                        logging.debug(u"GRANT {} ON ALL TABLES IN SCHEMA {} TO {};".format(
                            ', '.join(map(str, mapping[role]['grant'])), schem, role))
                conn_db_temp.commit()
                cur_tmp.close()
                conn_db_temp.close()
            conn_db.commit()
            cur.close()


    def WhoToAddPgsql(pgsql_users, ldap_users):
        change_users = {}
        ldap_all_users = []
        for role, value in ldap_users.items():
            ldap_all_users = ldap_all_users + value
        change_users['add'] = sorted(set(ldap_all_users) - set(pgsql_users))
        change_users['del'] = sorted((set(pgsql_users) - set(tech_users)) - set(ldap_all_users))
        logging.info(u'DELETE User: {}'.format(change_users['del']))
        logging.info(u'ADD User: {}'.format(change_users['add']))
        return change_users


    def ChangeUserInPgsql(users, role):
        cur = conn_db.cursor()
        for delete in users['del']:
            cur.execute('DROP USER "{}"'.format(delete))
            logging.debug(u'DROP USER "{}"'.format(delete))
        for new in users['add']:
            cur.execute('CREATE USER "{}" IN ROLE "{}"'.format(new, role))
            logging.debug(u'CREATE USER "{}" IN ROLE "{}"'.format(new, role))
        conn_db.commit()
        cur.close()


    if args['run'] == 'sync':
        ChekOrAdd(GetRoles(), GetAllBaseAndSchem())
        ChangeUserInPgsql(WhoToAddPgsql(GetAllUserPgsql(), SearchUserAdGroup(GroupLdapBind())), GetDefaultRole())
    elif args['run'] == 'analyz':
        print(WhoToAddPgsql(GetAllUserPgsql(), SearchUserAdGroup(GroupLdapBind())))

    conn_db.close()

except Exception as error:

    logging.error(traceback.format_exc())
    print(error)
