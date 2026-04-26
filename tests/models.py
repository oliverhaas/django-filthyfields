from django.db import models
from django.db.models.signals import pre_save
from django.utils import timezone as django_timezone

from filthyfields import DirtyFieldsMixin
from filthyfields.compare import timezone_support_compare


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


class JSONFieldTrackMutationsModel(DirtyFieldsMixin, models.Model):
    """Variant with TRACK_MUTATIONS enabled — detects in-place mutations of mutable values."""

    TRACK_MUTATIONS = True

    json_field = models.JSONField(default=dict)


class ModelWithFieldsToCheck(DirtyFieldsMixin, models.Model):
    """Model that only tracks specific fields."""

    FIELDS_TO_CHECK = ["boolean1"]

    boolean1 = models.BooleanField(default=True)
    boolean2 = models.BooleanField(default=True)


class ModelWithFieldsToCheckExclude(DirtyFieldsMixin, models.Model):
    """Model that tracks all fields except excluded ones."""

    FIELDS_TO_CHECK_EXCLUDE = ["boolean2"]

    boolean1 = models.BooleanField(default=True)
    boolean2 = models.BooleanField(default=True)


# M2M field tracking models
class Many2ManyModelTest(DirtyFieldsMixin, models.Model):
    m2m_field = models.ManyToManyField(ModelTest)
    ENABLE_M2M_CHECK = True


class Many2ManyWithoutMany2ManyModeEnabledModelTest(DirtyFieldsMixin, models.Model):
    m2m_field = models.ManyToManyField(ModelTest, related_name="m2m_disabled")


class M2MModelWithCustomPKOnM2MTest(DirtyFieldsMixin, models.Model):
    m2m_field = models.ManyToManyField(ModelWithCustomPKTest)


class ModelWithoutM2MCheckTest(DirtyFieldsMixin, models.Model):
    characters = models.CharField(blank=True, max_length=80)
    ENABLE_M2M_CHECK = False


class ModelWithM2MAndSpecifiedFieldsTest(DirtyFieldsMixin, models.Model):
    m2m1 = models.ManyToManyField(ModelTest, related_name="m2m1")
    m2m2 = models.ManyToManyField(ModelTest, related_name="m2m2")
    ENABLE_M2M_CHECK = True
    FIELDS_TO_CHECK = ["m2m1"]


# Compare function models (for timezone-aware datetime comparison)
class DatetimeWithCompareModelTest(DirtyFieldsMixin, models.Model):
    """Model with custom compare function for timezone-aware datetime fields."""

    datetime_field = models.DateTimeField(default=django_timezone.now)
    compare_function = (timezone_support_compare, {})


class CurrentDatetimeModelTest(DirtyFieldsMixin, models.Model):
    """Model with compare function that uses current timezone."""

    datetime_field = models.DateTimeField(default=django_timezone.now)
    compare_function = (
        timezone_support_compare,
        {"timezone_to_set": django_timezone.get_current_timezone()},
    )


# Custom-callable hooks (covers the (callable, kwargs) tuple contract for
# compare_function and normalise_function — outside the timezone helper).
def _abs_equal(new_value, old_value, *, tolerance=0):
    """Equal if absolute values match within tolerance."""
    return abs(abs(new_value) - abs(old_value)) <= tolerance


def _to_str(value):
    """Coerce to str for output normalisation."""
    return str(value) if value is not None else None


class CompareFunctionCustomCallableModel(DirtyFieldsMixin, models.Model):
    compare_function = (_abs_equal, {"tolerance": 1})

    int_field = models.IntegerField(default=0)


class NormaliseFunctionCustomCallableModel(DirtyFieldsMixin, models.Model):
    normalise_function = (_to_str, {})

    int_field = models.IntegerField(default=0)
