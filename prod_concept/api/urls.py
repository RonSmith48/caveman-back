from django.urls import path
from prod_concept.api.views.upload_concept import *
from prod_concept.api.views.views import EmptyView
from prod_concept.api.views.choose_parent import ChooseParentView

urlpatterns = [
    path('', EmptyView.as_view(), name='empty-view'),
    path('choose-parent/<int:location_id>/',
         ChooseParentView.as_view(), name='choose-parent'),
    path('upload/concept/', UploadConceptRingsView.as_view(), name='upload-concept'),
]
