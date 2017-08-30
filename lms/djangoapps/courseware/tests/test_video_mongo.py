# -*- coding: utf-8 -*-
"""Video xmodule tests in mongo."""

import json
from collections import OrderedDict
from uuid import uuid4

import ddt
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from edxval.api import ValCannotCreateError, ValVideoNotFoundError, create_profile, create_video, get_video_info
from lxml import etree
from mock import MagicMock, Mock, patch
from nose.plugins.attrib import attr
from path import Path as path

from xmodule.contentstore.content import StaticContent
from xmodule.exceptions import NotFoundError
from xmodule.modulestore.inheritance import own_metadata
from xmodule.modulestore.tests.django_utils import TEST_DATA_MONGO_MODULESTORE, TEST_DATA_SPLIT_MODULESTORE
from xmodule.tests.test_import import DummySystem
from xmodule.tests.test_video import VideoDescriptorTestBase, instantiate_descriptor
from xmodule.video_module import VideoDescriptor, bumper_utils, rewrite_video_url, video_utils
from xmodule.video_module.transcripts_utils import Transcript, save_to_store
from xmodule.x_module import STUDENT_VIEW

from .helpers import BaseTestXmodule
from .test_video_handlers import TestVideo
from .test_video_xml import SOURCE_XML

@attr(shard=1)
class TestVideoYouTube(TestVideo):
    METADATA = {}

    def test_video_constructor(self):
        """Make sure that all parameters extracted correctly from xml"""
        context = self.item_descriptor.render(STUDENT_VIEW).content
        sources = [u'example.mp4', u'example.webm']

        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
        }

        self.assertEqual(
            context,
            self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context),
        )


@attr(shard=1)
class TestVideoNonYouTube(TestVideo):
    """Integration tests: web client + mongo."""
    DATA = """
        <video show_captions="true"
        display_name="A Name"
        sub="a_sub_file.srt.sjson"
        download_video="true"
        start_time="01:00:03" end_time="01:00:10"
        >
            <source src="example.mp4"/>
            <source src="example.webm"/>
        </video>
    """
    MODEL_DATA = {
        'data': DATA,
    }
    METADATA = {}

    def test_video_constructor(self):
        """Make sure that if the 'youtube' attribute is omitted in XML, then
            the template generates an empty string for the YouTube streams.
        """
        context = self.item_descriptor.render(STUDENT_VIEW).content
        sources = [u'example.mp4', u'example.webm']

        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '1.00:3_yD_cEKoCk',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
        }

        self.assertEqual(
            context,
            self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context),
        )


@attr(shard=1)
@ddt.ddt
class TestGetHtmlMethod(BaseTestXmodule):
    '''
    Make sure that `get_html` works correctly.
    '''
    CATEGORY = "video"
    DATA = SOURCE_XML
    METADATA = {}

    def setUp(self):
        super(TestGetHtmlMethod, self).setUp()
        self.setup_course()
        self.default_metadata_dict = OrderedDict({
            'autoAdvance': False,
            'saveStateUrl': '',
            'autoplay': settings.FEATURES.get('AUTOPLAY_VIDEOS', True),
            'streams': '1.00:3_yD_cEKoCk',
            'sub': 'a_sub_file.srt.sjson',
            'sources': '[]',
            'poster': None,
            'captionDataDir': None,
            'showCaptions': 'true',
            'generalSpeed': 1.0,
            'speed': None,
            'savedVideoPosition': 0.0,
            'start': 3603.0,
            'end': 3610.0,
            'transcriptLanguage': 'en',
            'transcriptLanguages': OrderedDict({'en': 'English'}),
            'ytTestTimeout': 1500,
            'ytApiUrl': 'https://www.youtube.com/iframe_api',
            'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
            'ytKey': None,
            'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'translation/__lang__'
            ).rstrip('/?'),
            'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'available_translations'
            ).rstrip('/?'),
            'autohideHtml5': False,
            'recordedYoutubeIsAvailable': True,
        })

    def test_get_html_track(self):
        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
                sub="{sub}" download_track="{download_track}"
            start_time="01:00:03" end_time="01:00:10" download_video="true"
            >
                <source src="example.mp4"/>
                <source src="example.webm"/>
                {track}
                {transcripts}
            </video>
        """

        cases = [
            {
                'download_track': u'true',
                'track': u'<track src="http://www.example.com/track"/>',
                'sub': u'a_sub_file.srt.sjson',
                'expected_track_url': u'http://www.example.com/track',
                'transcripts': '',
            },
            {
                'download_track': u'true',
                'track': u'',
                'sub': u'a_sub_file.srt.sjson',
                'expected_track_url': u'a_sub_file.srt.sjson',
                'transcripts': '',
            },
            {
                'download_track': u'true',
                'track': u'',
                'sub': u'',
                'expected_track_url': None,
                'transcripts': '',
            },
            {
                'download_track': u'false',
                'track': u'<track src="http://www.example.com/track"/>',
                'sub': u'a_sub_file.srt.sjson',
                'expected_track_url': None,
                'transcripts': '',
            },
            {
                'download_track': u'true',
                'track': u'',
                'sub': u'',
                'expected_track_url': u'a_sub_file.srt.sjson',
                'transcripts': '<transcript language="uk" src="ukrainian.srt" />',
            },
        ]
        sources = [u'example.mp4', u'example.webm']

        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'metadata': '',
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
        }

        for data in cases:
            metadata = self.default_metadata_dict
            metadata['sources'] = sources
            DATA = SOURCE_XML.format(
                download_track=data['download_track'],
                track=data['track'],
                sub=data['sub'],
                transcripts=data['transcripts'],
            )

            self.initialize_module(data=DATA)
            track_url = self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'download'
            ).rstrip('/?')

            context = self.item_descriptor.render(STUDENT_VIEW).content
            metadata.update({
                'transcriptLanguages': {"en": "English"} if not data['transcripts'] else {"uk": u'Українська'},
                'transcriptLanguage': u'en' if not data['transcripts'] or data.get('sub') else u'uk',
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'sub': data['sub'],
            })
            expected_context.update({
                'transcript_download_format': (
                    None if self.item_descriptor.track and self.item_descriptor.download_track else u'srt'
                ),
                'track': (
                    track_url if data['expected_track_url'] == u'a_sub_file.srt.sjson' else data['expected_track_url']
                ),
                'id': self.item_descriptor.location.html_id(),
                'metadata': json.dumps(metadata)
            })

            self.assertEqual(
                context,
                self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context),
            )

    def test_get_html_source(self):
        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
            sub="a_sub_file.srt.sjson" source="{source}"
            download_video="{download_video}"
            start_time="01:00:03" end_time="01:00:10"
            >
                {sources}
            </video>
        """
        cases = [
            # self.download_video == True
            {
                'download_video': 'true',
                'source': 'example_source.mp4',
                'sources': """
                    <source src="example.mp4"/>
                    <source src="example.webm"/>
                """,
                'result': {
                    'download_video_link': u'example_source.mp4',
                    'sources': [u'example.mp4', u'example.webm'],
                },
            },
            {
                'download_video': 'true',
                'source': '',
                'sources': """
                    <source src="example.mp4"/>
                    <source src="example.webm"/>
                """,
                'result': {
                    'download_video_link': u'example.mp4',
                    'sources': [u'example.mp4', u'example.webm'],
                },
            },
            {
                'download_video': 'true',
                'source': '',
                'sources': [],
                'result': {},
            },

            # self.download_video == False
            {
                'download_video': 'false',
                'source': 'example_source.mp4',
                'sources': """
                    <source src="example.mp4"/>
                    <source src="example.webm"/>
                """,
                'result': {
                    'sources': [u'example.mp4', u'example.webm'],
                },
            },
        ]

        initial_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'metadata': self.default_metadata_dict,
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
        }

        for data in cases:
            DATA = SOURCE_XML.format(
                download_video=data['download_video'],
                source=data['source'],
                sources=data['sources']
            )
            self.initialize_module(data=DATA)
            context = self.item_descriptor.render(STUDENT_VIEW).content

            expected_context = dict(initial_context)
            expected_context['metadata'].update({
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'sources': data['result'].get('sources', []),
            })
            expected_context.update({
                'id': self.item_descriptor.location.html_id(),
                'download_video_link': data['result'].get('download_video_link'),
                'metadata': json.dumps(expected_context['metadata'])
            })

            self.assertEqual(
                context,
                self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
            )

    def test_get_html_with_non_existent_edx_video_id(self):
        """
        Tests the VideoModule get_html where a edx_video_id is given but a video is not found
        """
        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
            sub="a_sub_file.srt.sjson" source="{source}"
            download_video="{download_video}"
            start_time="01:00:03" end_time="01:00:10"
            edx_video_id="{edx_video_id}"
            >
                {sources}
            </video>
        """
        no_video_data = {
            'download_video': 'true',
            'source': 'example_source.mp4',
            'sources': """
            <source src="example.mp4"/>
            <source src="example.webm"/>
            """,
            'edx_video_id': "meow",
            'result': {
                'download_video_link': u'example_source.mp4',
                'sources': [u'example.mp4', u'example.webm'],
            }
        }
        DATA = SOURCE_XML.format(
            download_video=no_video_data['download_video'],
            source=no_video_data['source'],
            sources=no_video_data['sources'],
            edx_video_id=no_video_data['edx_video_id']
        )
        self.initialize_module(data=DATA)

        # Referencing a non-existent VAL ID in courseware won't cause an error --
        # it'll just fall back to the values in the VideoDescriptor.
        self.assertIn("example_source.mp4", self.item_descriptor.render(STUDENT_VIEW).content)

    def test_get_html_with_mocked_edx_video_id(self):
        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
            sub="a_sub_file.srt.sjson" source="{source}"
            download_video="{download_video}"
            start_time="01:00:03" end_time="01:00:10"
            edx_video_id="{edx_video_id}"
            >
                {sources}
            </video>
        """

        data = {
            # test with download_video set to false and make sure download_video_link is not set (is None)
            'download_video': 'false',
            'source': 'example_source.mp4',
            'sources': """
                <source src="example.mp4"/>
                <source src="example.webm"/>
            """,
            'edx_video_id': "mock item",
            'result': {
                'download_video_link': None,
                # make sure the desktop_mp4 url is included as part of the alternative sources.
                'sources': [u'example.mp4', u'example.webm', u'http://www.meowmix.com'],
            }
        }

        # Video found for edx_video_id
        metadata = self.default_metadata_dict
        metadata['autoplay'] = False
        metadata['sources'] = ""
        initial_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
            'metadata': metadata
        }

        DATA = SOURCE_XML.format(
            download_video=data['download_video'],
            source=data['source'],
            sources=data['sources'],
            edx_video_id=data['edx_video_id']
        )
        self.initialize_module(data=DATA)

        with patch('edxval.api.get_video_info') as mock_get_video_info:
            mock_get_video_info.return_value = {
                'url': '/edxval/video/example',
                'edx_video_id': u'example',
                'duration': 111.0,
                'client_video_id': u'The example video',
                'encoded_videos': [
                    {
                        'url': u'http://www.meowmix.com',
                        'file_size': 25556,
                        'bitrate': 9600,
                        'profile': u'desktop_mp4'
                    }
                ]
            }
            context = self.item_descriptor.render(STUDENT_VIEW).content

        expected_context = dict(initial_context)
        expected_context['metadata'].update({
            'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'translation/__lang__'
            ).rstrip('/?'),
            'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'available_translations'
            ).rstrip('/?'),
            'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
            'sources': data['result']['sources'],
        })
        expected_context.update({
            'id': self.item_descriptor.location.html_id(),
            'download_video_link': data['result']['download_video_link'],
            'metadata': json.dumps(expected_context['metadata'])
        })

        self.assertEqual(
            context,
            self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        )

    def test_get_html_with_existing_edx_video_id(self):
        """
        Tests the `VideoModule` `get_html` where `edx_video_id` is given and related video is found
        """
        edx_video_id = 'thundercats'
        # create video with provided edx_video_id and return encoded_videos
        encoded_videos = self.encode_and_create_video(edx_video_id)
        # data to be used to retrieve video by edxval API
        data = {
            'download_video': 'true',
            'source': 'example_source.mp4',
            'sources': """
                <source src="example.mp4"/>
                <source src="example.webm"/>
            """,
            'edx_video_id': edx_video_id,
            'result': {
                'download_video_link': u'http://fake-video.edx.org/{}.mp4'.format(edx_video_id),
                'sources': [u'example.mp4', u'example.webm'] + [video['url'] for video in encoded_videos],
            },
        }
        # context returned by get_html when provided with above data
        # expected_context, a dict to assert with context
        context, expected_context = self.helper_get_html_with_edx_video_id(data)
        self.assertEqual(
            context,
            self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        )

    def test_get_html_with_existing_unstripped_edx_video_id(self):
        """
        Tests the `VideoModule` `get_html` where `edx_video_id` with some unwanted tab(\t)
        is given and related video is found
        """
        edx_video_id = 'thundercats'
        # create video with provided edx_video_id and return encoded_videos
        encoded_videos = self.encode_and_create_video(edx_video_id)
        # data to be used to retrieve video by edxval API
        # unstripped edx_video_id is provided here
        data = {
            'download_video': 'true',
            'source': 'example_source.mp4',
            'sources': """
                <source src="example.mp4"/>
                <source src="example.webm"/>
            """,
            'edx_video_id': "{}\t".format(edx_video_id),
            'result': {
                'download_video_link': u'http://fake-video.edx.org/{}.mp4'.format(edx_video_id),
                'sources': [u'example.mp4', u'example.webm'] + [video['url'] for video in encoded_videos],
            },
        }
        # context returned by get_html when provided with above data
        # expected_context, a dict to assert with context
        context, expected_context = self.helper_get_html_with_edx_video_id(data)
        self.assertEqual(
            context,
            self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        )

    def encode_and_create_video(self, edx_video_id):
        """
        Create and encode video to be used for tests
        """
        encoded_videos = []
        for profile, extension in [("desktop_webm", "webm"), ("desktop_mp4", "mp4")]:
            create_profile(profile)
            encoded_videos.append(
                dict(
                    url=u"http://fake-video.edx.org/{}.{}".format(edx_video_id, extension),
                    file_size=9000,
                    bitrate=42,
                    profile=profile,
                )
            )
        result = create_video(
            dict(
                client_video_id='A Client Video id',
                duration=111,
                edx_video_id=edx_video_id,
                status='test',
                encoded_videos=encoded_videos,
            )
        )
        self.assertEqual(result, edx_video_id)
        return encoded_videos

    def helper_get_html_with_edx_video_id(self, data):
        """
        Create expected context and get actual context returned by `get_html` method.
        """
        # make sure the urls for the various encodings are included as part of the alternative sources.
        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
            sub="a_sub_file.srt.sjson" source="{source}"
            download_video="{download_video}"
            start_time="01:00:03" end_time="01:00:10"
            edx_video_id="{edx_video_id}"
            >
                {sources}
            </video>
        """

        # Video found for edx_video_id
        metadata = self.default_metadata_dict
        metadata['sources'] = ""
        initial_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
            'metadata': metadata,
        }

        # pylint: disable=invalid-name
        DATA = SOURCE_XML.format(
            download_video=data['download_video'],
            source=data['source'],
            sources=data['sources'],
            edx_video_id=data['edx_video_id']
        )
        self.initialize_module(data=DATA)
        # context returned by get_html
        context = self.item_descriptor.render(STUDENT_VIEW).content

        # expected_context, expected context to be returned by get_html
        expected_context = dict(initial_context)
        expected_context['metadata'].update({
            'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'translation/__lang__'
            ).rstrip('/?'),
            'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                self.item_descriptor, 'transcript', 'available_translations'
            ).rstrip('/?'),
            'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
            'sources': data['result']['sources'],
        })
        expected_context.update({
            'id': self.item_descriptor.location.html_id(),
            'download_video_link': data['result']['download_video_link'],
            'metadata': json.dumps(expected_context['metadata'])
        })
        return context, expected_context

    # pylint: disable=invalid-name
    @patch('xmodule.video_module.video_module.BrandingInfoConfig')
    @patch('xmodule.video_module.video_module.rewrite_video_url')
    def test_get_html_cdn_source(self, mocked_get_video, mock_BrandingInfoConfig):
        """
        Test if sources got from CDN
        """

        mock_BrandingInfoConfig.get_config.return_value = {
            "CN": {
                'url': 'http://www.xuetangx.com',
                'logo_src': 'http://www.xuetangx.com/static/images/logo.png',
                'logo_tag': 'Video hosted by XuetangX.com'
            }
        }

        def side_effect(*args, **kwargs):
            cdn = {
                'http://example.com/example.mp4': 'http://cdn-example.com/example.mp4',
                'http://example.com/example.webm': 'http://cdn-example.com/example.webm',
            }
            return cdn.get(args[1])

        mocked_get_video.side_effect = side_effect

        SOURCE_XML = """
            <video show_captions="true"
            display_name="A Name"
            sub="a_sub_file.srt.sjson" source="{source}"
            download_video="{download_video}"
            edx_video_id="{edx_video_id}"
            start_time="01:00:03" end_time="01:00:10"
            >
                {sources}
            </video>
        """

        case_data = {
            'download_video': 'true',
            'source': 'example_source.mp4',
            'sources': """
                <source src="http://example.com/example.mp4"/>
                <source src="http://example.com/example.webm"/>
            """,
            'result': {
                'download_video_link': u'example_source.mp4',
                'sources': [
                    u'http://cdn-example.com/example.mp4',
                    u'http://cdn-example.com/example.webm'
                ],
            },
        }

        # test with and without edx_video_id specified.
        cases = [
            dict(case_data, edx_video_id=""),
            dict(case_data, edx_video_id="vid-v1:12345"),
        ]

        initial_context = {
            'autoadvance_enabled': False,
            'branding_info': {
                'logo_src': 'http://www.xuetangx.com/static/images/logo.png',
                'logo_tag': 'Video hosted by XuetangX.com',
                'url': 'http://www.xuetangx.com'
            },
            'license': None,
            'bumper_metadata': 'null',
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': None,
            'handout': None,
            'id': None,
            'metadata': self.default_metadata_dict,
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null',
        }

        for data in cases:
            DATA = SOURCE_XML.format(
                download_video=data['download_video'],
                source=data['source'],
                sources=data['sources'],
                edx_video_id=data['edx_video_id'],
            )
            self.initialize_module(data=DATA)
            self.item_descriptor.xmodule_runtime.user_location = 'CN'
            context = self.item_descriptor.render('student_view').content
            expected_context = dict(initial_context)
            expected_context['metadata'].update({
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'sources': data['result'].get('sources', []),
            })
            expected_context.update({
                'id': self.item_descriptor.location.html_id(),
                'download_video_link': data['result'].get('download_video_link'),
                'metadata': json.dumps(expected_context['metadata'])
            })

            self.assertEqual(
                context,
                self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
            )

    @ddt.data(
        (True, ['youtube', 'desktop_webm', 'desktop_mp4', 'hls']),
        (False, ['youtube', 'desktop_webm', 'desktop_mp4'])
    )
    @ddt.unpack
    def test_get_html_on_toggling_hls_feature(self, hls_feature_enabled, expected_val_profiles):
        """
        Verify val profiles on toggling HLS Playback feature.
        """
        with patch('xmodule.video_module.video_module.edxval_api.get_urls_for_profiles') as get_urls_for_profiles:
            get_urls_for_profiles.return_value = {
                'desktop_webm': 'https://webm.com/dw.webm',
                'hls': 'https://hls.com/hls.m3u8',
                'youtube': 'https://yt.com/?v=v0TFmdO4ZP0',
                'desktop_mp4': 'https://mp4.com/dm.mp4'
            }
            with patch('xmodule.video_module.video_module.HLSPlaybackEnabledFlag.feature_enabled') as feature_enabled:
                feature_enabled.return_value = hls_feature_enabled
                video_xml = '<video display_name="Video" download_video="true" edx_video_id="12345-67890">[]</video>'
                self.initialize_module(data=video_xml)
                self.item_descriptor.render(STUDENT_VIEW)
                get_urls_for_profiles.assert_called_with(
                    self.item_descriptor.edx_video_id,
                    expected_val_profiles,
                )

    @patch('xmodule.video_module.video_module.HLSPlaybackEnabledFlag.feature_enabled', Mock(return_value=True))
    @patch('xmodule.video_module.video_module.edxval_api.get_urls_for_profiles')
    def test_get_html_hls(self, get_urls_for_profiles):
        """
        Verify that hls profile functionality works as expected.

        * HLS source should be added into list of available sources
        * HLS source should not be used for download URL If available from edxval
        """
        video_xml = '<video display_name="Video" download_video="true" edx_video_id="12345-67890">[]</video>'

        get_urls_for_profiles.return_value = {
            'desktop_webm': 'https://webm.com/dw.webm',
            'hls': 'https://hls.com/hls.m3u8',
            'youtube': 'https://yt.com/?v=v0TFmdO4ZP0',
            'desktop_mp4': 'https://mp4.com/dm.mp4'
        }

        self.initialize_module(data=video_xml)
        context = self.item_descriptor.render(STUDENT_VIEW).content

        self.assertIn("'download_video_link': 'https://mp4.com/dm.mp4'", context)
        self.assertIn('"streams": "1.00:https://yt.com/?v=v0TFmdO4ZP0"', context)
        self.assertIn(
            '"sources": ["https://webm.com/dw.webm", "https://mp4.com/dm.mp4", "https://hls.com/hls.m3u8"]', context
        )

    def test_get_html_hls_no_video_id(self):
        """
        Verify that `download_video_link` is set to None for HLS videos if no video id
        """
        video_xml = """
        <video display_name="Video" download_video="true" source="https://hls.com/hls.m3u8">
        ["https://hls.com/hls2.m3u8", "https://hls.com/hls3.m3u8"]
        </video>
        """

        self.initialize_module(data=video_xml)
        context = self.item_descriptor.render(STUDENT_VIEW).content
        self.assertIn("'download_video_link': None", context)

    @patch('xmodule.video_module.video_module.edxval_api.get_course_video_image_url')
    def test_poster_image(self, get_course_video_image_url):
        """
        Verify that poster image functionality works as expected.
        """
        video_xml = '<video display_name="Video" download_video="true" edx_video_id="12345-67890">[]</video>'
        get_course_video_image_url.return_value = '/media/video-images/poster.png'

        self.initialize_module(data=video_xml)
        context = self.item_descriptor.render(STUDENT_VIEW).content

        self.assertIn('"poster": "/media/video-images/poster.png"', context)

    @patch('xmodule.video_module.video_module.edxval_api.get_course_video_image_url')
    def test_poster_image_without_edx_video_id(self, get_course_video_image_url):
        """
        Verify that poster image is set to None and there is no crash when no edx_video_id.
        """
        video_xml = '<video display_name="Video" download_video="true" edx_video_id="null">[]</video>'
        get_course_video_image_url.return_value = '/media/video-images/poster.png'

        self.initialize_module(data=video_xml)
        context = self.item_descriptor.render(STUDENT_VIEW).content

        self.assertIn("\'poster\': \'null\'", context)


@attr(shard=1)
class TestVideoCDNRewriting(BaseTestXmodule):
    """
    Tests for Video CDN.
    """

    def setUp(self, *args, **kwargs):
        super(TestVideoCDNRewriting, self).setUp(*args, **kwargs)
        self.original_video_file = "original_video.mp4"
        self.original_video_url = "http://www.originalvideo.com/" + self.original_video_file

    @patch.dict("django.conf.settings.CDN_VIDEO_URLS",
                {"CN": "https://chinacdn.cn/"})
    def test_rewrite_video_url_success(self):
        """
        Test successful CDN request.
        """
        cdn_response_video_url = settings.CDN_VIDEO_URLS["CN"] + self.original_video_file

        self.assertEqual(
            rewrite_video_url(settings.CDN_VIDEO_URLS["CN"], self.original_video_url),
            cdn_response_video_url
        )

    @patch.dict("django.conf.settings.CDN_VIDEO_URLS",
                {"CN": "https://chinacdn.cn/"})
    def test_rewrite_url_concat(self):
        """
        Test that written URLs are returned clean despite input
        """
        cdn_response_video_url = settings.CDN_VIDEO_URLS["CN"] + "original_video.mp4"

        self.assertEqual(
            rewrite_video_url(settings.CDN_VIDEO_URLS["CN"] + "///", self.original_video_url),
            cdn_response_video_url
        )

    def test_rewrite_video_url_invalid_url(self):
        """
        Test if no alternative video in CDN exists.
        """
        invalid_cdn_url = 'http://http://fakecdn.com/'
        self.assertIsNone(rewrite_video_url(invalid_cdn_url, self.original_video_url))

    def test_none_args(self):
        """
        Ensure None args return None
        """
        self.assertIsNone(rewrite_video_url(None, None))

    def test_emptystring_args(self):
        """
        Ensure emptyrstring args return None
        """
        self.assertIsNone(rewrite_video_url("", ""))


@attr(shard=1)
@ddt.ddt
class TestVideoDescriptorInitialization(BaseTestXmodule):
    """
    Make sure that module initialization works correctly.
    """
    CATEGORY = "video"
    DATA = SOURCE_XML
    METADATA = {}

    def setUp(self):
        super(TestVideoDescriptorInitialization, self).setUp()
        self.setup_course()

    def test_source_not_in_html5sources(self):
        metadata = {
            'source': 'http://example.org/video.mp4',
            'html5_sources': ['http://youtu.be/3_yD_cEKoCk.mp4'],
        }

        self.initialize_module(metadata=metadata)
        fields = self.item_descriptor.editable_metadata_fields

        self.assertIn('source', fields)
        self.assertEqual(self.item_descriptor.source, 'http://example.org/video.mp4')
        self.assertTrue(self.item_descriptor.download_video)
        self.assertTrue(self.item_descriptor.source_visible)

    def test_source_in_html5sources(self):
        metadata = {
            'source': 'http://example.org/video.mp4',
            'html5_sources': ['http://example.org/video.mp4'],
        }

        self.initialize_module(metadata=metadata)
        fields = self.item_descriptor.editable_metadata_fields

        self.assertNotIn('source', fields)
        self.assertTrue(self.item_descriptor.download_video)
        self.assertFalse(self.item_descriptor.source_visible)

    def test_download_video_is_explicitly_set(self):
        metadata = {
            'track': u'http://some_track.srt',
            'source': 'http://example.org/video.mp4',
            'html5_sources': ['http://youtu.be/3_yD_cEKoCk.mp4'],
            'download_video': False,
        }

        self.initialize_module(metadata=metadata)

        fields = self.item_descriptor.editable_metadata_fields
        self.assertIn('source', fields)
        self.assertIn('download_video', fields)

        self.assertFalse(self.item_descriptor.download_video)
        self.assertTrue(self.item_descriptor.source_visible)
        self.assertTrue(self.item_descriptor.download_track)

    def test_source_is_empty(self):
        metadata = {
            'source': '',
            'html5_sources': ['http://youtu.be/3_yD_cEKoCk.mp4'],
        }

        self.initialize_module(metadata=metadata)
        fields = self.item_descriptor.editable_metadata_fields

        self.assertNotIn('source', fields)
        self.assertFalse(self.item_descriptor.download_video)

    @ddt.data(
        (
            {
                'desktop_webm': 'https://webm.com/dw.webm',
                'hls': 'https://hls.com/hls.m3u8',
                'youtube': 'v0TFmdO4ZP0',
                'desktop_mp4': 'https://mp4.com/dm.mp4'
            },
            ['https://www.youtube.com/watch?v=v0TFmdO4ZP0']
        ),
        (
            {
                'desktop_webm': 'https://webm.com/dw.webm',
                'hls': 'https://hls.com/hls.m3u8',
                'youtube': None,
                'desktop_mp4': 'https://mp4.com/dm.mp4'
            },
            ['https://hls.com/hls.m3u8']
        ),
        (
            {
                'desktop_webm': 'https://webm.com/dw.webm',
                'hls': None,
                'youtube': None,
                'desktop_mp4': 'https://mp4.com/dm.mp4'
            },
            ['https://mp4.com/dm.mp4']
        ),
        (
            {
                'desktop_webm': 'https://webm.com/dw.webm',
                'hls': None,
                'youtube': None,
                'desktop_mp4': None
            },
            ['https://webm.com/dw.webm']
        ),
        (
            {
                'desktop_webm': None,
                'hls': None,
                'youtube': None,
                'desktop_mp4': None
            },
            ['https://www.youtube.com/watch?v=3_yD_cEKoCk']
        ),
    )
    @ddt.unpack
    @patch('xmodule.video_module.video_module.HLSPlaybackEnabledFlag.feature_enabled', Mock(return_value=True))
    def test_val_encoding_in_context(self, val_video_encodings, video_url):
        """
        Tests that the val encodings correctly override the video url when the edx video id is set and
        one or more encodings are present.
        """
        with patch('xmodule.video_module.video_module.edxval_api.get_urls_for_profiles') as get_urls_for_profiles:
            get_urls_for_profiles.return_value = val_video_encodings
            self.initialize_module(
                data='<video display_name="Video" download_video="true" edx_video_id="12345-67890">[]</video>'
            )
            context = self.item_descriptor.get_context()
            self.assertEqual(context['transcripts_basic_tab_metadata']['video_url']['value'], video_url)


@attr(shard=1)
@ddt.ddt
class TestEditorSavedMethod(BaseTestXmodule):
    """
    Make sure that `editor_saved` method works correctly.
    """
    CATEGORY = "video"
    DATA = SOURCE_XML
    METADATA = {}

    def setUp(self):
        super(TestEditorSavedMethod, self).setUp()
        self.setup_course()
        self.metadata = {
            'source': 'http://youtu.be/3_yD_cEKoCk',
            'html5_sources': ['http://example.org/video.mp4'],
        }
        # path to subs_3_yD_cEKoCk.srt.sjson file
        self.file_name = 'subs_3_yD_cEKoCk.srt.sjson'
        # pylint: disable=no-value-for-parameter
        self.test_dir = path(__file__).abspath().dirname().dirname().dirname().dirname().dirname()
        self.file_path = self.test_dir + '/common/test/data/uploads/' + self.file_name

    @ddt.data(TEST_DATA_MONGO_MODULESTORE, TEST_DATA_SPLIT_MODULESTORE)
    def test_editor_saved_when_html5_sub_not_exist(self, default_store):
        """
        When there is youtube_sub exist but no html5_sub present for
        html5_sources, editor_saved function will generate new html5_sub
        for video.
        """
        self.MODULESTORE = default_store  # pylint: disable=invalid-name
        self.initialize_module(metadata=self.metadata)
        item = self.store.get_item(self.item_descriptor.location)
        with open(self.file_path, "r") as myfile:
            save_to_store(myfile.read(), self.file_name, 'text/sjson', item.location)
        item.sub = "3_yD_cEKoCk"
        # subs_video.srt.sjson does not exist before calling editor_saved function
        with self.assertRaises(NotFoundError):
            Transcript.get_asset(item.location, 'subs_video.srt.sjson')
        old_metadata = own_metadata(item)
        # calling editor_saved will generate new file subs_video.srt.sjson for html5_sources
        item.editor_saved(self.user, old_metadata, None)
        self.assertIsInstance(Transcript.get_asset(item.location, 'subs_3_yD_cEKoCk.srt.sjson'), StaticContent)
        self.assertIsInstance(Transcript.get_asset(item.location, 'subs_video.srt.sjson'), StaticContent)

    @ddt.data(TEST_DATA_MONGO_MODULESTORE, TEST_DATA_SPLIT_MODULESTORE)
    def test_editor_saved_when_youtube_and_html5_subs_exist(self, default_store):
        """
        When both youtube_sub and html5_sub already exist then no new
        sub will be generated by editor_saved function.
        """
        self.MODULESTORE = default_store
        self.initialize_module(metadata=self.metadata)
        item = self.store.get_item(self.item_descriptor.location)
        with open(self.file_path, "r") as myfile:
            save_to_store(myfile.read(), self.file_name, 'text/sjson', item.location)
            save_to_store(myfile.read(), 'subs_video.srt.sjson', 'text/sjson', item.location)
        item.sub = "3_yD_cEKoCk"
        # subs_3_yD_cEKoCk.srt.sjson and subs_video.srt.sjson already exist
        self.assertIsInstance(Transcript.get_asset(item.location, self.file_name), StaticContent)
        self.assertIsInstance(Transcript.get_asset(item.location, 'subs_video.srt.sjson'), StaticContent)
        old_metadata = own_metadata(item)
        with patch('xmodule.video_module.video_module.manage_video_subtitles_save') as manage_video_subtitles_save:
            item.editor_saved(self.user, old_metadata, None)
            self.assertFalse(manage_video_subtitles_save.called)

    @ddt.data(TEST_DATA_MONGO_MODULESTORE, TEST_DATA_SPLIT_MODULESTORE)
    def test_editor_saved_with_unstripped_video_id(self, default_store):
        """
        Verify editor saved when video id contains spaces/tabs.
        """
        self.MODULESTORE = default_store
        stripped_video_id = unicode(uuid4())
        unstripped_video_id = u'{video_id}{tabs}'.format(video_id=stripped_video_id, tabs=u'\t\t\t')
        self.metadata.update({
            'edx_video_id': unstripped_video_id
        })
        self.initialize_module(metadata=self.metadata)
        item = self.store.get_item(self.item_descriptor.location)
        self.assertEqual(item.edx_video_id, unstripped_video_id)

        # Now, modifying and saving the video module should strip the video id.
        old_metadata = own_metadata(item)
        item.display_name = u'New display name'
        item.editor_saved(self.user, old_metadata, None)
        self.assertEqual(item.edx_video_id, stripped_video_id)

    @ddt.data(TEST_DATA_MONGO_MODULESTORE, TEST_DATA_SPLIT_MODULESTORE)
    @patch('xmodule.video_module.video_module.edxval_api.get_url_for_profile', Mock(return_value='test_yt_id'))
    def test_editor_saved_with_yt_val_profile(self, default_store):
        """
        Verify editor saved overrides `youtube_id_1_0` when a youtube val profile is there
        for a given `edx_video_id`.
        """
        self.MODULESTORE = default_store
        self.initialize_module(metadata=self.metadata)
        item = self.store.get_item(self.item_descriptor.location)
        self.assertEqual(item.youtube_id_1_0, '3_yD_cEKoCk')

        # Now, modify `edx_video_id` and save should override `youtube_id_1_0`.
        old_metadata = own_metadata(item)
        item.edx_video_id = unicode(uuid4())
        item.editor_saved(self.user, old_metadata, None)
        self.assertEqual(item.youtube_id_1_0, 'test_yt_id')


@ddt.ddt
class TestVideoDescriptorStudentViewJson(TestCase):
    """
    Tests for the student_view_data method on VideoDescriptor.
    """
    TEST_DURATION = 111.0
    TEST_PROFILE = "mobile"
    TEST_SOURCE_URL = "http://www.example.com/source.mp4"
    TEST_LANGUAGE = "ge"
    TEST_ENCODED_VIDEO = {
        'profile': TEST_PROFILE,
        'bitrate': 333,
        'url': 'http://example.com/video',
        'file_size': 222,
    }
    TEST_EDX_VIDEO_ID = 'test_edx_video_id'
    TEST_YOUTUBE_ID = 'test_youtube_id'
    TEST_YOUTUBE_EXPECTED_URL = 'https://www.youtube.com/watch?v=test_youtube_id'

    def setUp(self):
        super(TestVideoDescriptorStudentViewJson, self).setUp()
        video_declaration = "<video display_name='Test Video' youtube_id_1_0=\'" + self.TEST_YOUTUBE_ID + "\'>"
        sample_xml = ''.join([
            video_declaration,
            "<source src='", self.TEST_SOURCE_URL, "'/> ",
            "<transcript language='", self.TEST_LANGUAGE, "' src='german_translation.srt' /> ",
            "</video>"]
        )
        self.transcript_url = "transcript_url"
        self.video = instantiate_descriptor(data=sample_xml)
        self.video.runtime.handler_url = Mock(return_value=self.transcript_url)

    def setup_val_video(self, associate_course_in_val=False):
        """
        Creates a video entry in VAL.
        Arguments:
            associate_course - If True, associates the test course with the video in VAL.
        """
        create_profile('mobile')
        create_video({
            'edx_video_id': self.TEST_EDX_VIDEO_ID,
            'client_video_id': 'test_client_video_id',
            'duration': self.TEST_DURATION,
            'status': 'dummy',
            'encoded_videos': [self.TEST_ENCODED_VIDEO],
            'courses': [unicode(self.video.location.course_key)] if associate_course_in_val else [],
        })
        self.val_video = get_video_info(self.TEST_EDX_VIDEO_ID)  # pylint: disable=attribute-defined-outside-init

    def get_result(self, allow_cache_miss=True):
        """
        Returns the result from calling the video's student_view_data method.
        Arguments:
            allow_cache_miss is passed in the context to the student_view_data method.
        """
        context = {
            "profiles": [self.TEST_PROFILE],
            "allow_cache_miss": "True" if allow_cache_miss else "False"
        }
        return self.video.student_view_data(context)

    def verify_result_with_fallback_and_youtube(self, result):
        """
        Verifies the result is as expected when returning "fallback" video data (not from VAL).
        """
        self.assertDictEqual(
            result,
            {
                "only_on_web": False,
                "duration": None,
                "transcripts": {self.TEST_LANGUAGE: self.transcript_url},
                "encoded_videos": {
                    "fallback": {"url": self.TEST_SOURCE_URL, "file_size": 0},
                    "youtube": {"url": self.TEST_YOUTUBE_EXPECTED_URL, "file_size": 0}
                },
            }
        )

    def verify_result_with_youtube_url(self, result):
        """
        Verifies the result is as expected when returning "fallback" video data (not from VAL).
        """
        self.assertDictEqual(
            result,
            {
                "only_on_web": False,
                "duration": None,
                "transcripts": {self.TEST_LANGUAGE: self.transcript_url},
                "encoded_videos": {"youtube": {"url": self.TEST_YOUTUBE_EXPECTED_URL, "file_size": 0}},
            }
        )

    def verify_result_with_val_profile(self, result):
        """
        Verifies the result is as expected when returning video data from VAL.
        """
        self.assertDictContainsSubset(
            result.pop("encoded_videos")[self.TEST_PROFILE],
            self.TEST_ENCODED_VIDEO,
        )
        self.assertDictEqual(
            result,
            {
                "only_on_web": False,
                "duration": self.TEST_DURATION,
                "transcripts": {self.TEST_LANGUAGE: self.transcript_url},
            }
        )

    def test_only_on_web(self):
        self.video.only_on_web = True
        result = self.get_result()
        self.assertDictEqual(result, {"only_on_web": True})

    def test_no_edx_video_id(self):
        result = self.get_result()
        self.verify_result_with_fallback_and_youtube(result)

    def test_no_edx_video_id_and_no_fallback(self):
        video_declaration = "<video display_name='Test Video' youtube_id_1_0=\'{}\'>".format(self.TEST_YOUTUBE_ID)
        # the video has no source listed, only a youtube link, so no fallback url will be provided
        sample_xml = ''.join([
            video_declaration,
            "<transcript language='", self.TEST_LANGUAGE, "' src='german_translation.srt' /> ",
            "</video>"
        ])
        self.transcript_url = "transcript_url"
        self.video = instantiate_descriptor(data=sample_xml)
        self.video.runtime.handler_url = Mock(return_value=self.transcript_url)
        result = self.get_result()
        self.verify_result_with_youtube_url(result)

    @ddt.data(True, False)
    def test_with_edx_video_id_video_associated_in_val(self, allow_cache_miss):
        """
        Tests retrieving a video that is stored in VAL and associated with a course in VAL.
        """
        self.video.edx_video_id = self.TEST_EDX_VIDEO_ID
        self.setup_val_video(associate_course_in_val=True)
        # the video is associated in VAL so no cache miss should ever happen but test retrieval in both contexts
        result = self.get_result(allow_cache_miss)
        self.verify_result_with_val_profile(result)

    @ddt.data(True, False)
    def test_with_edx_video_id_video_unassociated_in_val(self, allow_cache_miss):
        """
        Tests retrieving a video that is stored in VAL but not associated with a course in VAL.
        """
        self.video.edx_video_id = self.TEST_EDX_VIDEO_ID
        self.setup_val_video(associate_course_in_val=False)
        result = self.get_result(allow_cache_miss)
        if allow_cache_miss:
            self.verify_result_with_val_profile(result)
        else:
            self.verify_result_with_fallback_and_youtube(result)

    @ddt.data(True, False)
    def test_with_edx_video_id_video_not_in_val(self, allow_cache_miss):
        """
        Tests retrieving a video that is not stored in VAL.
        """
        self.video.edx_video_id = self.TEST_EDX_VIDEO_ID
        # The video is not in VAL so in contexts that do and don't allow cache misses we should always get a fallback
        result = self.get_result(allow_cache_miss)
        self.verify_result_with_fallback_and_youtube(result)


@attr(shard=1)
class VideoDescriptorTest(TestCase, VideoDescriptorTestBase):
    """
    Tests for video descriptor that requires access to django settings.
    """
    def setUp(self):
        super(VideoDescriptorTest, self).setUp()
        self.descriptor.runtime.handler_url = MagicMock()
        self.descriptor.runtime.course_id = MagicMock()

    def test_get_context(self):
        """"
        Test get_context.

        This test is located here and not in xmodule.tests because get_context calls editable_metadata_fields.
        Which, in turn, uses settings.LANGUAGES from django setttings.
        """
        correct_tabs = [
            {
                'name': "Basic",
                'template': "video/transcripts.html",
                'current': True
            },
            {
                'name': 'Advanced',
                'template': 'tabs/metadata-edit-tab.html'
            }
        ]
        rendered_context = self.descriptor.get_context()
        self.assertListEqual(rendered_context['tabs'], correct_tabs)

        # Assert that the Video ID field is present in basic tab metadata context.
        self.assertEqual(
            rendered_context['transcripts_basic_tab_metadata']['edx_video_id'],
            self.descriptor.editable_metadata_fields['edx_video_id']
        )

    def test_export_val_data(self):
        self.descriptor.edx_video_id = 'test_edx_video_id'
        create_profile('mobile')
        create_video({
            'edx_video_id': self.descriptor.edx_video_id,
            'client_video_id': 'test_client_video_id',
            'duration': 111,
            'status': 'dummy',
            'encoded_videos': [{
                'profile': 'mobile',
                'url': 'http://example.com/video',
                'file_size': 222,
                'bitrate': 333,
            }],
        })

        actual = self.descriptor.definition_to_xml(resource_fs=None)
        expected_str = """
            <video download_video="false" url_name="SampleProblem">
                <video_asset client_video_id="test_client_video_id" duration="111.0" image="">
                    <encoded_video profile="mobile" url="http://example.com/video" file_size="222" bitrate="333"/>
                </video_asset>
            </video>
        """
        parser = etree.XMLParser(remove_blank_text=True)
        expected = etree.XML(expected_str, parser=parser)
        self.assertXmlEqual(expected, actual)

    def test_export_val_data_not_found(self):
        self.descriptor.edx_video_id = 'nonexistent'
        actual = self.descriptor.definition_to_xml(resource_fs=None)
        expected_str = """<video download_video="false" url_name="SampleProblem"/>"""
        parser = etree.XMLParser(remove_blank_text=True)
        expected = etree.XML(expected_str, parser=parser)
        self.assertXmlEqual(expected, actual)

    def test_import_val_data(self):
        create_profile('mobile')
        module_system = DummySystem(load_error_modules=True)

        xml_data = """
            <video edx_video_id="test_edx_video_id">
                <video_asset client_video_id="test_client_video_id" duration="111.0">
                    <encoded_video profile="mobile" url="http://example.com/video" file_size="222" bitrate="333"/>
                </video_asset>
            </video>
        """
        id_generator = Mock()
        id_generator.target_course_id = "test_course_id"
        video = VideoDescriptor.from_xml(xml_data, module_system, id_generator)
        self.assertEqual(video.edx_video_id, 'test_edx_video_id')
        video_data = get_video_info(video.edx_video_id)
        self.assertEqual(video_data['client_video_id'], 'test_client_video_id')
        self.assertEqual(video_data['duration'], 111)
        self.assertEqual(video_data['status'], 'imported')
        self.assertEqual(video_data['courses'], [{id_generator.target_course_id: None}])
        self.assertEqual(video_data['encoded_videos'][0]['profile'], 'mobile')
        self.assertEqual(video_data['encoded_videos'][0]['url'], 'http://example.com/video')
        self.assertEqual(video_data['encoded_videos'][0]['file_size'], 222)
        self.assertEqual(video_data['encoded_videos'][0]['bitrate'], 333)

    def test_import_val_data_invalid(self):
        create_profile('mobile')
        module_system = DummySystem(load_error_modules=True)

        # Negative file_size is invalid
        xml_data = """
            <video edx_video_id="test_edx_video_id">
                <video_asset client_video_id="test_client_video_id" duration="111.0">
                    <encoded_video profile="mobile" url="http://example.com/video" file_size="-222" bitrate="333"/>
                </video_asset>
            </video>
        """
        with self.assertRaises(ValCannotCreateError):
            VideoDescriptor.from_xml(xml_data, module_system, id_generator=Mock())
        with self.assertRaises(ValVideoNotFoundError):
            get_video_info("test_edx_video_id")


class TestVideoWithBumper(TestVideo):
    """
    Tests rendered content in presence of video bumper.
    """
    CATEGORY = "video"
    METADATA = {}
    FEATURES = settings.FEATURES

    @patch('xmodule.video_module.bumper_utils.get_bumper_settings')
    def test_is_bumper_enabled(self, get_bumper_settings):
        """
        Check that bumper is (not)shown if ENABLE_VIDEO_BUMPER is (False)True

        Assume that bumper settings are correct.
        """
        self.FEATURES.update({
            "SHOW_BUMPER_PERIODICITY": 1,
            "ENABLE_VIDEO_BUMPER": True,
        })

        get_bumper_settings.return_value = {
            "video_id": "edx_video_id",
            "transcripts": {},
        }
        with override_settings(FEATURES=self.FEATURES):
            self.assertTrue(bumper_utils.is_bumper_enabled(self.item_descriptor))

        self.FEATURES.update({"ENABLE_VIDEO_BUMPER": False})

        with override_settings(FEATURES=self.FEATURES):
            self.assertFalse(bumper_utils.is_bumper_enabled(self.item_descriptor))

    @patch('xmodule.video_module.bumper_utils.is_bumper_enabled')
    @patch('xmodule.video_module.bumper_utils.get_bumper_settings')
    @patch('edxval.api.get_urls_for_profiles')
    def test_bumper_metadata(self, get_url_for_profiles, get_bumper_settings, is_bumper_enabled):
        """
        Test content with rendered bumper metadata.
        """
        get_url_for_profiles.return_value = {
            'desktop_mp4': 'http://test_bumper.mp4',
            'desktop_webm': '',
        }

        get_bumper_settings.return_value = {
            'video_id': 'edx_video_id',
            'transcripts': {},
        }

        is_bumper_enabled.return_value = True

        content = self.item_descriptor.render(STUDENT_VIEW).content
        sources = [u'example.mp4', u'example.webm']
        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'bumper_metadata': json.dumps(OrderedDict({
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'showCaptions': 'true',
                'sources': ['http://test_bumper.mp4'],
                'streams': '',
                'transcriptLanguage': 'en',
                'transcriptLanguages': {'en': 'English'},
                'transcriptTranslationUrl': video_utils.set_query_parameter(
                    self.item_descriptor.xmodule_runtime.handler_url(
                        self.item_descriptor, 'transcript', 'translation/__lang__'
                    ).rstrip('/?'), 'is_bumper', 1
                ),
                'transcriptAvailableTranslationsUrl': video_utils.set_query_parameter(
                    self.item_descriptor.xmodule_runtime.handler_url(
                        self.item_descriptor, 'transcript', 'available_translations'
                    ).rstrip('/?'), 'is_bumper', 1
                ),
            })),
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': json.dumps(OrderedDict({
                'url': 'http://img.youtube.com/vi/ZwkTiUPN0mg/0.jpg',
                'type': 'youtube'
            }))
        }

        expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        self.assertEqual(content, expected_content)


class TestAutoAdvanceVideo(TestVideo):
    """
    Tests the server side of video auto-advance.

    We check the availability of auto-advance (feature flag) and the value of the
    setting for the current video when the course enables it (course-level,
    advanced setting).
    But: we don't check what happens with the course-level setting when the feature
    is globally disabled, because the feature is disabled and the course-level
    setting has no meaning and shouldn't be used.
    """
    CATEGORY = "video"
    METADATA = {}
    FEATURES = settings.FEATURES
    # FIXME remove maxDiff line
    maxDiff = None

    def change_course_setting_autoadvance(self, new_value):
        """
        Change the .video_auto_advance course setting (a.k.a. advanced setting).
        This avoids doing .save(), and instead modifies the instance directly.
        Based on test code for video_bumper setting.
        """
        # This first render is done to initialize the instance
        self.item_descriptor.render(STUDENT_VIEW)
        item_instance = self.item_descriptor.xmodule_runtime.xmodule_instance
        item_instance.video_auto_advance = new_value
        # After this step, render() should see the new value
        # e.g. use self.item_descriptor.render(STUDENT_VIEW).content

    def test_is_autoadvance_enabled(self):
        """
        Check that the autoadvance is not available when it is disabled via feature flag
        (ENABLE_AUTOADVANCE_VIDEOS set to False). Then change the feature flag to True and
        check that it shows as enabled.
        """
        self.FEATURES.update({
            "ENABLE_AUTOADVANCE_VIDEOS": False,
        })

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content

        sources = [u'example.mp4', u'example.webm']
        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'bumper_metadata': 'null',
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null'
        }

        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)

        self.assertEqual(content, expected_content)

        # Enable flag and check that it's enabled
        self.FEATURES.update({"ENABLE_AUTOADVANCE_VIDEOS": True})

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content
        expected_context['autoadvance_enabled'] = True
        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        self.assertEqual(content, expected_content)

    def test_is_autoadvance_available(self):
        """
        Check that the autoadvance is not available when it is disabled via feature flag
        (ENABLE_AUTOADVANCE_VIDEOS set to False). Then change the feature flag to True and
        check that it shows as enabled.
        This doesn't say whether the current video will auto-advance or not, just whether
        the controls will be available.
        """
        self.FEATURES.update({
            "ENABLE_AUTOADVANCE_VIDEOS": False,
        })

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content

        sources = [u'example.mp4', u'example.webm']
        expected_context = {
            'autoadvance_enabled': False,
            'branding_info': None,
            'license': None,
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'bumper_metadata': 'null',
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null'
        }

        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)

        self.assertEqual(content, expected_content)

        # Enable flag and check that it's enabled
        self.FEATURES.update({"ENABLE_AUTOADVANCE_VIDEOS": True})

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content
        expected_context['autoadvance_enabled'] = True
        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        self.assertEqual(content, expected_content)

    def test_autoadvance_in_video_depends_from_course_advanced_settings(self):
        """
        Check that the course-level settings (advanced settings) impact whether
        the current video will auto-advance or not. This test presumes
        video-advance is globally enabled.
        """
        self.FEATURES.update({
            "ENABLE_AUTOADVANCE_VIDEOS": True,
        })

        # enable at course-level, set to true
        self.change_course_setting_autoadvance(new_value=True)

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content


        sources = [u'example.mp4', u'example.webm']
        expected_context = {
            'autoadvance_enabled': True,
            'branding_info': None,
            'license': None,
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'bumper_metadata': 'null',
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': True,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null'
        }

        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)

        self.assertEqual(content, expected_content)

        # Now disable at course-level and check that it's disabled
        self.change_course_setting_autoadvance(new_value=False)

        # same as before, but with autoAdvance:False
        expected_context = {
            'autoadvance_enabled': True,
            'branding_info': None,
            'license': None,
            'cdn_eval': False,
            'cdn_exp_group': None,
            'display_name': u'A Name',
            'download_video_link': u'example.mp4',
            'handout': None,
            'id': self.item_descriptor.location.html_id(),
            'bumper_metadata': 'null',
            'metadata': json.dumps(OrderedDict({
                'autoAdvance': False,
                'saveStateUrl': self.item_descriptor.xmodule_runtime.ajax_url + '/save_user_state',
                'autoplay': False,
                'streams': '0.75:jNCf2gIqpeE,1.00:ZwkTiUPN0mg,1.25:rsq9auxASqI,1.50:kMyNdzVHHgg',
                'sub': 'a_sub_file.srt.sjson',
                'sources': sources,
                'poster': None,
                'captionDataDir': None,
                'showCaptions': 'true',
                'generalSpeed': 1.0,
                'speed': None,
                'savedVideoPosition': 0.0,
                'start': 3603.0,
                'end': 3610.0,
                'transcriptLanguage': 'en',
                'transcriptLanguages': OrderedDict({'en': 'English', 'uk': u'Українська'}),
                'ytTestTimeout': 1500,
                'ytApiUrl': 'https://www.youtube.com/iframe_api',
                'ytMetadataUrl': 'https://www.googleapis.com/youtube/v3/videos/',
                'ytKey': None,
                'transcriptTranslationUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'translation/__lang__'
                ).rstrip('/?'),
                'transcriptAvailableTranslationsUrl': self.item_descriptor.xmodule_runtime.handler_url(
                    self.item_descriptor, 'transcript', 'available_translations'
                ).rstrip('/?'),
                'autohideHtml5': False,
                'recordedYoutubeIsAvailable': True,
            })),
            'track': None,
            'transcript_download_format': u'srt',
            'transcript_download_formats_list': [
                {'display_name': 'SubRip (.srt) file', 'value': 'srt'},
                {'display_name': 'Text (.txt) file', 'value': 'txt'}
            ],
            'poster': 'null'
        }

        with override_settings(FEATURES=self.FEATURES):
            content = self.item_descriptor.render(STUDENT_VIEW).content
        with override_settings(FEATURES=self.FEATURES):
            expected_content = self.item_descriptor.xmodule_runtime.render_template('video.html', expected_context)
        self.assertEqual(content, expected_content)
