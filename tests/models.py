from django.db import models
from django.db.models.signals import pre_save
from django.utils import timezone as django_timezone

from dirtyfields import DirtyFieldsMixin


class ModelTest(DirtyFieldsMixin, models.Model):
    """A simple test model to test dirty fields mixin with"""

    boolean = models.BooleanField(default=True)
    characters = models.CharField(blank=True, max_length=80)


class ModelWithDecimalFieldTest(DirtyFieldsMixin, models.Model):
    decimal_field = models.DecimalField(decimal_places=2, max_digits=10)


class ModelWithForeignKeyTest(DirtyFieldsMixin, models.Model):
    fkey = models.ForeignKey(ModelTest, on_delete=models.CASCADE)


class MixedFieldsModelTest(DirtyFieldsMixin, models.Model):
    fkey = models.ForeignKey(ModelTest, on_delete=models.CASCADE)
    characters = models.CharField(blank=True, max_length=80)


class ModelWithOneToOneFieldTest(DirtyFieldsMixin, models.Model):
    o2o = models.OneToOneField(ModelTest, on_delete=models.CASCADE)


class ModelWithNonEditableFieldsTest(DirtyFieldsMixin, models.Model):
    dt = models.DateTimeField(auto_now_add=True)
    characters = models.CharField(blank=True, max_length=80, editable=False)
    boolean = models.BooleanField(default=True)


class ModelWithSelfForeignKeyTest(DirtyFieldsMixin, models.Model):
    fkey = models.ForeignKey("self", blank=True, null=True, on_delete=models.CASCADE)


class OrdinaryModelTest(models.Model):
    boolean = models.BooleanField(default=True)
    characters = models.CharField(blank=True, max_length=80)


class OrdinaryWithDirtyFieldsProxy(DirtyFieldsMixin, OrdinaryModelTest):
    class Meta:
        proxy = True


class OrdinaryModelWithForeignKeyTest(models.Model):
    fkey = models.ForeignKey(OrdinaryModelTest, on_delete=models.CASCADE)


class SubclassModelTest(ModelTest):
    pass


class ExpressionModelTest(DirtyFieldsMixin, models.Model):
    counter = models.IntegerField(default=0)


class DatetimeModelTest(DirtyFieldsMixin, models.Model):
    datetime_field = models.DateTimeField(default=django_timezone.now)


class ModelWithCustomPKTest(DirtyFieldsMixin, models.Model):
    custom_primary_key = models.CharField(max_length=80, primary_key=True)


class WithPreSaveSignalModelTest(DirtyFieldsMixin, models.Model):
    data = models.CharField(max_length=255)
    data_updated_on_presave = models.CharField(max_length=255, blank=True, null=True)

    @staticmethod
    def pre_save(instance, *args, **kwargs):
        dirty_fields = instance.get_dirty_fields()
        if "data" in dirty_fields and "specific_value" in instance.data:
            instance.data_updated_on_presave = "presave_value"


pre_save.connect(
    WithPreSaveSignalModelTest.pre_save,
    sender=WithPreSaveSignalModelTest,
    dispatch_uid="WithPreSaveSignalModelTest__pre_save",
)


class DoubleForeignKeyModelTest(DirtyFieldsMixin, models.Model):
    fkey1 = models.ForeignKey(ModelTest, on_delete=models.CASCADE)
    fkey2 = models.ForeignKey(
        ModelTest,
        null=True,
        related_name="fkey2",
        on_delete=models.CASCADE,
    )


class BinaryModelTest(DirtyFieldsMixin, models.Model):
    bytea = models.BinaryField()


class FileFieldModel(DirtyFieldsMixin, models.Model):
    file1 = models.FileField(upload_to="file1/")


class ImageFieldModel(DirtyFieldsMixin, models.Model):
    image1 = models.ImageField(upload_to="image1/")


class JSONFieldModel(DirtyFieldsMixin, models.Model):
    json_field = models.JSONField(default=dict)
