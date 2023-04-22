import qbittorrentapi

# from django.test import TestCase


# Create your tests here.
client = qbittorrentapi.Client(
    host='http://100.64.152.70',
    port=8998,
    username='ngfchl',
    password='.wq891222',
    SIMPLE_RESPONSES=True
)
# client = transmission_rpc.Client(
#     host='100.64.152.70',
#     port=9091,
#     username='ngfchl',
#     password='.wq891222',
# )
# session = client.get_session(15)
#
# print('===='*32)
# print(client.session_stats().fields)


client.auth_log_in()
res = client.torrents_properties(torrent_hash='7a46d98b5cb6031f47aa1c1ae771c165fdbf8ad6')
print(res)
res2 = client.torrents_trackers(torrent_hash='7a46d98b5cb6031f47aa1c1ae771c165fdbf8ad6')
print(res2)
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
