from rest_framework import viewsets

from apps.core.permissions import HasModulePermission
from apps.core.tenant import filter_queryset_for_user, get_user_company, user_is_global_admin


class TenantModelViewSet(viewsets.ModelViewSet):
    permission_classes = [HasModulePermission]
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        queryset = super().get_queryset()

        return filter_queryset_for_user(
            queryset=queryset,
            user=self.request.user,
            company_field=self.tenant_filter_path,
        )

    def perform_create(self, serializer):
        user = self.request.user

        if user_is_global_admin(user):
            serializer.save()
            return

        company = get_user_company(user)

        if company and self.tenant_create_field:
            field_names = set(serializer.fields.keys())

            if self.tenant_create_field in field_names:
                serializer.save(**{self.tenant_create_field: company})
                return

        serializer.save()


class TenantQuerysetMixin:
    tenant_filter_path = "id_company"

    def get_queryset(self):
        queryset = super().get_queryset()

        return filter_queryset_for_user(
            queryset=queryset,
            user=self.request.user,
            company_field=self.tenant_filter_path,
        )
