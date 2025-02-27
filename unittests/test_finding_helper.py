from .dojo_test_case import DojoTestCase
from dojo.models import Finding, Test, Vulnerability_Id, Finding_Template, Vulnerability_Id_Template
from django.contrib.auth.models import User
from unittest import mock
from unittest.mock import patch
from crum import impersonate
import datetime
from django.utils import timezone
import logging
from dojo.finding.helper import save_vulnerability_ids, save_vulnerability_ids_template

logger = logging.getLogger(__name__)


# frozen_datetime = timezone.make_aware(datetime.datetime(2021, 1, 1, 2, 2, 2), timezone.get_default_timezone())
frozen_datetime = timezone.now()


class TestUpdateFindingStatusSignal(DojoTestCase):
    fixtures = ['dojo_testdata.json']

    def setUp(self):
        self.user_1 = User.objects.get(id='1')
        self.user_2 = User.objects.get(id='2')

    def get_status_fields(self, finding):
        logger.debug('%s, %s, %s, %s, %s, %s, %s, %s', finding.active, finding.verified, finding.false_p, finding.out_of_scope, finding.is_mitigated, finding.mitigated, finding.mitigated_by, finding.last_status_update)
        return finding.active, finding.verified, finding.false_p, finding.out_of_scope, finding.is_mitigated, finding.mitigated, finding.mitigated_by, finding.last_status_update

    @mock.patch('dojo.finding.helper.timezone.now')
    def test_new_finding(self, mock_tz):
        mock_tz.return_value = frozen_datetime
        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test)
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (True, True, False, False, False, None, None, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    def test_no_status_change(self, mock_tz):
        mock_tz.return_value = frozen_datetime
        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test)
            finding.save()

            status_fields = self.get_status_fields(finding)

            finding.title = finding.title + '!!!'
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                status_fields
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    def test_mark_fresh_as_mitigated(self, mock_dt):
        mock_dt.return_value = frozen_datetime
        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test, is_mitigated=True, active=False)
            finding.save()
            self.assertEqual(
                self.get_status_fields(finding),
                (False, True, False, False, True, frozen_datetime, self.user_1, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=False)
    def test_mark_old_active_as_mitigated(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test, is_mitigated=True, active=False)
            finding.save()
            finding.is_mitigated = True
            finding.active = False
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (False, True, False, False, True, frozen_datetime, self.user_1, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=True)
    def test_mark_old_active_as_mitigated_custom_edit(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        custom_mitigated = datetime.datetime.now()

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test)
            finding.save()
            finding.is_mitigated = True
            finding.active = False
            finding.mitigated = custom_mitigated
            finding.mitigated_by = self.user_2
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (False, True, False, False, True, custom_mitigated, self.user_2, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=True)
    def test_update_old_mitigated_with_custom_edit(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        custom_mitigated = datetime.datetime.now()

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test, is_mitigated=True, active=False, mitigated=frozen_datetime, mitigated_by=self.user_1)
            finding.save()
            finding.is_mitigated = True
            finding.active = False
            finding.mitigated = custom_mitigated
            finding.mitigated_by = self.user_2
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (False, True, False, False, True, custom_mitigated, self.user_2, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=True)
    def test_update_old_mitigated_with_missing_data(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        custom_mitigated = datetime.datetime.now()

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test, is_mitigated=True, active=False, mitigated=custom_mitigated, mitigated_by=self.user_2)
            finding.save()
            finding.is_mitigated = True
            finding.active = False
            # trying to remove mitigated fields will trigger the signal to set them to now/current user
            finding.mitigated = None
            finding.mitigated_by = None
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (False, True, False, False, True, frozen_datetime, self.user_1, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=True)
    def test_set_old_mitigated_as_active(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test, is_mitigated=True, active=False, mitigated=frozen_datetime, mitigated_by=self.user_2)
            logger.debug('save1')
            finding.save()
            finding.active = True
            logger.debug('save2')
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                (True, True, False, False, False, None, None, frozen_datetime)
            )

    @mock.patch('dojo.finding.helper.timezone.now')
    @mock.patch('dojo.finding.helper.can_edit_mitigated_data', return_value=False)
    def test_set_active_as_false_p(self, mock_can_edit, mock_tz):
        mock_tz.return_value = frozen_datetime

        with impersonate(self.user_1):
            test = Test.objects.last()
            finding = Finding(test=test)
            finding.save()
            finding.false_p = True
            finding.save()

            self.assertEqual(
                self.get_status_fields(finding),
                # TODO marking as false positive resets verified to False, possible bug / undesired behaviour?
                (False, False, True, False, True, frozen_datetime, self.user_1, frozen_datetime)
            )


class TestSaveVulnerabilityIds(DojoTestCase):

    @patch('dojo.finding.helper.Vulnerability_Id.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id.delete')
    def test_previous_vr_and_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding()
        previous_vulnerability_ids = [
            Vulnerability_Id(id=1, finding=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = ['REF-2']

        save_vulnerability_ids(finding, new_vulnerability_ids)

        self.assertEqual('REF-2', finding.cve)
        mock_filter.assert_called_once_with(finding=finding)
        mock_create.assert_called_once_with(finding=finding, vulnerability_id='REF-2')
        mock_delete.assert_called_once()

    @patch('dojo.finding.helper.Vulnerability_Id.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id.delete')
    def test_previous_vr_and_no_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding()
        previous_vulnerability_ids = [
            Vulnerability_Id(id=1, finding=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = []

        save_vulnerability_ids(finding, new_vulnerability_ids)

        self.assertEqual(None, finding.cve)
        mock_filter.assert_called_once_with(finding=finding)
        mock_create.assert_not_called()
        mock_delete.assert_called_once()

    @patch('dojo.finding.helper.Vulnerability_Id.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id.delete')
    def test_no_previous_vr_and_no_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding()
        previous_vulnerability_ids = []
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = []

        save_vulnerability_ids(finding, new_vulnerability_ids)

        self.assertEqual(None, finding.cve)
        mock_filter.assert_called_once_with(finding=finding)
        mock_create.assert_not_called()
        mock_delete.assert_not_called()

    @patch('dojo.finding.helper.Vulnerability_Id.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id.delete')
    def test_same_previous_vr_and_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding()
        previous_vulnerability_ids = [
            Vulnerability_Id(id=1, finding=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = Vulnerability_Id(id=1, finding=finding, vulnerability_id='REF-1'), False

        new_vulnerability_ids = ['REF-1']

        save_vulnerability_ids(finding, new_vulnerability_ids)

        self.assertEqual('REF-1', finding.cve)
        mock_filter.assert_called_once_with(finding=finding)
        mock_create.assert_called_once_with(finding=finding, vulnerability_id='REF-1')
        mock_delete.assert_not_called()


class TestSaveVulnerabilityIdsTemplate(DojoTestCase):

    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.delete')
    def test_previous_vr_and_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding_Template()
        previous_vulnerability_ids = [
            Vulnerability_Id_Template(id=1, finding_template=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = ['REF-2']

        save_vulnerability_ids_template(finding, new_vulnerability_ids)

        self.assertEqual('REF-2', finding.cve)
        mock_filter.assert_called_once_with(finding_template=finding)
        mock_create.assert_called_once_with(finding_template=finding, vulnerability_id='REF-2')
        mock_delete.assert_called_once()

    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.delete')
    def test_previous_vr_and_no_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding_Template()
        previous_vulnerability_ids = [
            Vulnerability_Id_Template(id=1, finding_template=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = []

        save_vulnerability_ids_template(finding, new_vulnerability_ids)

        self.assertEqual(None, finding.cve)
        mock_filter.assert_called_once_with(finding_template=finding)
        mock_create.assert_not_called()
        mock_delete.assert_called_once()

    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.delete')
    def test_no_previous_vr_and_no_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding_Template()
        previous_vulnerability_ids = []
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = None, True

        new_vulnerability_ids = []

        save_vulnerability_ids_template(finding, new_vulnerability_ids)

        self.assertEqual(None, finding.cve)
        mock_filter.assert_called_once_with(finding_template=finding)
        mock_create.assert_not_called()
        mock_delete.assert_not_called()

    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.filter')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.objects.get_or_create')
    @patch('dojo.finding.helper.Vulnerability_Id_Template.delete')
    def test_same_previous_vr_and_new_vr(self, mock_delete, mock_create, mock_filter):
        finding = Finding_Template()
        previous_vulnerability_ids = [
            Vulnerability_Id_Template(id=1, finding_template=finding, vulnerability_id='REF-1'),
        ]
        mock_filter.return_value = previous_vulnerability_ids
        mock_create.return_value = Vulnerability_Id_Template(id=1, finding_template=finding, vulnerability_id='REF-1'), False

        new_vulnerability_ids = ['REF-1']

        save_vulnerability_ids_template(finding, new_vulnerability_ids)

        self.assertEqual('REF-1', finding.cve)
        mock_filter.assert_called_once_with(finding_template=finding)
        mock_create.assert_called_once_with(finding_template=finding, vulnerability_id='REF-1')
        mock_delete.assert_not_called()
