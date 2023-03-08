import qbittorrentapi
import transmission_rpc

# from django.test import TestCase


# Create your tests here.
# client = qbittorrentapi.Client(
#     host='100.97.181.90',
#     port=8999,
#     username='ngfchl',
#     password='.wq891222',
#     SIMPLE_RESPONSES=True
# )
client = transmission_rpc.Client(
    host='100.64.152.70',
    port=9091,
    username='ngfchl',
    password='.wq891222',
)
session = client.get_session(15)

print('===='*32)
print(client.session_stats().fields)






# client.auth_log_in()
# categories = client.torrents_categories()
# print('===='*32)
# print(categories)
# print('===='*32)
#
# print(client.application.buildInfo)
# print('===='*32)
#
# print(client.torrents.info.all())
# print('===='*32)
#
# print(client.sync_maindata())
# print('===='*32)
#
# print(client.transfer_info())
