import django_filters
from .models import *
from rest_framework import filters


class ProductFilter(django_filters.FilterSet):
    vendor_name = django_filters.CharFilter(field_name='user__name', lookup_expr='icontains')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')


    class Meta:
        model = Product
        fields = {
            'user': ['exact'],
            'name': ['iexact', 'icontains'],
            'slug': ['iexact', 'icontains'],
            'category': ['exact'],
            'created_at': ['exact', 'gt', 'lt', 'range'],
            'updated_at': ['exact', 'gt', 'lt', 'range']
            }
        

class InStockFilterVendorProduct(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return queryset.filter(stock__gt=0)