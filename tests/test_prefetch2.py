from rest_framework.test import APITestCase

from dynamic_rest.prefetch import FastQuery, FastPrefetch
from dynamic_rest.utils.profiling import get_cpu_usage
from tests.models import (
    Group,
    Location,
    Profile,
    User
)
from tests.setup import create_fixture


class TestPrefetch(APITestCase):

    def setUp(self):
        self.fixture = create_fixture()

    def _user_keys(self):
        return set([
            'last_name',
            'name',
            'favorite_pet_id',
            'date_of_birth',
            'favorite_pet_type_id',
            'location_id',
            'id'
        ])

    def test_fk_prefetch(self):
        with self.assertNumQueries(2):
            q = FastQuery(User.objects.all())
            q.prefetch_related(
                FastPrefetch(
                    'location',
                    Location.objects.all()
                )
            )
            result = q.execute()

        self.assertTrue(
            all([_['location'] for _ in result])
        )
        self.assertEquals(
            set(['blob', 'id', 'name']),
            set(result[0]['location'].keys())
        )

    def test_m2m_prefetch(self):
        with self.assertNumQueries(3):
            q = FastQuery(User.objects.all())
            q.prefetch_related(
                FastPrefetch(
                    'groups',
                    Group.objects.all()
                )
            )
            result = q.execute()

        self.assertTrue(
            all([_['groups'] for _ in result])
        )
        self.assertTrue(
            isinstance(result[0]['groups'], list)
        )
        self.assertEquals(
            set(['id', 'name']),
            set(result[0]['groups'][0].keys())
        )

    def test_o2o_prefetch(self):
        # Create profiles
        for i in range(1, 4):
            Profile.objects.create(
                user=User.objects.get(pk=i),
                display_name='User %s' % i
            )

        with self.assertNumQueries(2):
            q = FastQuery(Profile.objects.all())
            q.prefetch_related(
                FastPrefetch(
                    'user',
                    User.objects.all()
                )
            )
            result = q.execute()

        self.assertTrue(
            all([_['user'] for _ in result])
        )
        self.assertEquals(
            self._user_keys(),
            set(result[0]['user'].keys())
        )

    def test_reverse_o2o_prefetch(self):
        # Create profiles
        for i in range(1, 4):
            Profile.objects.create(
                user=User.objects.get(pk=i),
                display_name='User %s' % i
            )

        with self.assertNumQueries(2):
            q = FastQuery(User.objects.all())
            q.prefetch_related(
                FastPrefetch(
                    'profile',
                    Profile.objects.all()
                )
            )
            result = q.execute()

        self.assertTrue(
            all(['profile' in _ for _ in result])
        )
        user = sorted(
            result,
            key=lambda x: 1 if x['profile'] is None else 0
        )[0]
        self.assertEquals(
            set(['display_name', 'user_id', 'id', 'thumbnail_url']),
            set(user['profile'].keys())
        )

    def test_m2o_prefetch(self):
        with self.assertNumQueries(2):
            q = FastQuery(Location.objects.all())
            q.prefetch_related(
                FastPrefetch(
                    'user_set',
                    User.objects.all()
                )
            )
            result = q.execute()

        self.assertTrue(
            all(['user_set' in obj for obj in result])
        )
        location = (
            o for o in result if o['user_set'] and len(o['user_set']) > 1
        ).next()

        self.assertIsNotNone(location)
        self.assertEquals(
            self._user_keys(),
            set(location['user_set'][0].keys())
        )

    def test_pagination(self):
        r = list(FastQuery(User.objects.all()))
        self.assertTrue(isinstance(r, list))

        r = FastQuery(User.objects.order_by('id'))[1]
        self.assertEquals(1, len(r))
        self.assertEquals(r[0]['id'], 2)

        r = FastQuery(User.objects.order_by('id'))[1:3]
        self.assertEquals(2, len(r))
        self.assertEquals(r[0]['id'], 2)
        self.assertEquals(r[1]['id'], 3)

        with self.assertRaises(TypeError):
            FastQuery(User.objects.all())[:10:2]

    def test_nested_prefetch_by_string(self):
        q = FastQuery(Location.objects.filter(pk=1))
        q.prefetch_related('user_set__groups')
        out = list(q)

        self.assertTrue('user_set' in out[0])
        self.assertTrue('groups' in out[0]['user_set'][0])

    def test_api(self):
        url = (
            '/users/?include[]=groups.&include[]=profile.&include[]=location.'
        )

        s1 = get_cpu_usage()
        for i in range(0, 100):
            self.client.get(url)
        e1 = get_cpu_usage()
        u1 = e1 - s1

        s2 = get_cpu_usage()
        url = url + '&make_fast=1'
        for i in range(0, 100):
            self.client.get(url)
        e2 = get_cpu_usage()
        u2 = e2 - s2

        self.assertEquals(
            u1, u2,
            "Slow: %.4f Fast: %.4f" % (u1, u2)
        )
