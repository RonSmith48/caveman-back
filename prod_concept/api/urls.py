from django.urls import path
from prod_concept.api.views.upload_concept import *
from prod_concept.api.views.views import EmptyView

urlpatterns = [
    path('', EmptyView.as_view(), name='empty-view'),
    path('upload/concept/', UploadConceptRingsView.as_view(), name='upload-concept'),
]
