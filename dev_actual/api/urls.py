from django.urls import path
import dev_actual.api.views as v


urlpatterns = [
    path('', v.EmptyView.as_view(), name='empty-view'),
]
