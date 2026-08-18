import json
import re

from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, ListView
from django_ratelimit.decorators import ratelimit

from utils.image_processing import variant_url
from utils.seo import absolute_url

from .cache_helpers import (
    available_colors,
    home_faqs,
    home_reviews,
    home_sections,
    nav_context,
    review_platforms,
)
from .models import Brand, Category, Vehicle
from .seo_copy import brand_heading, category_heading, has_extra_listing_filters


def _json_ld(data: dict) -> str:
    """Serialize JSON-LD safely for embedding in a <script> tag."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return mark_safe(payload.replace("<", "\\u003c"))


@method_decorator(
    cache_control(private=True, max_age=30, must_revalidate=True),
    name="dispatch",
)
class HomeView(ListView):
    model = Vehicle
    template_name = "catalog/home.html"
    context_object_name = "home_cars"
    HOME_SECTION_LIMIT = 10

    def get_queryset(self):
        return home_sections(self.HOME_SECTION_LIMIT)["home_cars"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(nav_context())
        sections = home_sections(self.HOME_SECTION_LIMIT)
        context["home_cars"] = sections["home_cars"]
        context["home_trucks"] = sections["home_trucks"]
        context["home_special"] = sections["home_special"]
        context["has_home_offers"] = bool(
            context["home_cars"] or context["home_trucks"] or context["home_special"]
        )
        context["available_colors"] = available_colors()
        context["home_faqs"] = home_faqs()
        context["home_reviews"] = home_reviews(limit=6)
        context["review_platforms"] = review_platforms()
        context["seo_title"] = "Автомобили под заказ из Китая | Техника Года"
        context["seo_description"] = (
            "Автомобили под заказ из Китая с площадки Техника Года. "
            "Проверка до оплаты, гарантия 6 месяцев на ДВС и КПП, цена под ключ до Благовещенска."
        )
        return context


@method_decorator(
    cache_control(private=True, max_age=30, must_revalidate=True),
    name="dispatch",
)
@method_decorator(ratelimit(key="ip", rate="90/m", method="GET", block=True), name="dispatch")
class VehicleListView(ListView):
    model = Vehicle
    template_name = "catalog/index.html"
    context_object_name = "vehicles"
    paginate_by = 10

    def category_slug(self):
        get_cat = (self.request.GET.get("category") or "").strip()
        if get_cat:
            return get_cat
        return self.kwargs.get("category_slug")

    def brand_slug(self):
        return self.kwargs.get("brand_slug") or self.request.GET.get("brand")

    def dispatch(self, request, *args, **kwargs):
        # Clean SEO routes already carry category/brand in the path.
        if kwargs.get("category_slug") or kwargs.get("brand_slug"):
            return super().dispatch(request, *args, **kwargs)

        # /catalog/cars/ with no filters → default cars category (clean URL).
        if not request.GET:
            return redirect(
                "catalog:category", category_slug="cars", permanent=False
            )

        # Single-dimension query filters → permanent redirect to clean URLs.
        keys = set(request.GET.keys())
        if keys == {"category"} and request.GET.get("category"):
            return redirect(
                "catalog:category",
                category_slug=request.GET["category"],
                permanent=True,
            )
        if keys == {"brand"} and request.GET.get("brand"):
            return redirect(
                "catalog:brand",
                brand_slug=request.GET["brand"],
                permanent=True,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Vehicle.objects.filter(is_published=True).select_related(
            "brand", "category"
        )
        params = self.request.GET

        category_slug = self.category_slug()
        if category_slug == "cars_new":
            queryset = queryset.filter(
                Q(category__slug="cars_new")
                | Q(category__parent__slug="cars")
                | Q(category__slug="cars"),
                mileage=0,
            ).exclude(Q(is_featured=True) | Q(category__slug="cars_bought"))
        elif category_slug == "cars_bought":
            cars_root = Category.objects.filter(slug="cars").first()
            cars_ids = cars_root.subtree_ids() if cars_root else set()
            queryset = queryset.filter(
                Q(category__slug="cars_bought")
                | Q(is_featured=True, category_id__in=cars_ids)
            )
        elif category_slug:
            category = Category.objects.filter(slug=category_slug).first()
            if category:
                queryset = queryset.filter(category_id__in=category.subtree_ids())
            elif self.kwargs.get("category_slug") == category_slug:
                raise Http404("Категория не найдена")
            else:
                queryset = queryset.none()

        body_type_slug = params.get("body_type")
        if body_type_slug:
            body_type_category = Category.objects.filter(slug=body_type_slug).first()
            if body_type_category:
                body_type_terms = {body_type_category.name.strip()}
                if body_type_category.name:
                    # "Седаны" -> "Седан", "Минивэны" -> "Минивэн".
                    if body_type_category.name[-1:].lower() in {"ы", "и"}:
                        body_type_terms.add(body_type_category.name[:-1].strip())
                body_type_terms |= {term.lower() for term in body_type_terms}
                body_type_q = Q()
                for term in filter(None, body_type_terms):
                    body_type_q |= Q(body_type__icontains=term)
                queryset = queryset.filter(
                    Q(category_id__in=body_type_category.subtree_ids()) | body_type_q
                )

        brand_slug = self.brand_slug()
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)

        year_from = params.get("year_from")
        year_to = params.get("year_to")
        if year_from and year_from.isdigit():
            queryset = queryset.filter(year__gte=int(year_from))
        if year_to and year_to.isdigit():
            queryset = queryset.filter(year__lte=int(year_to))

        mileage_to = params.get("mileage_to")
        if mileage_to and mileage_to.isdigit():
            queryset = queryset.filter(mileage__lte=int(mileage_to))

        price_from = params.get("price_from")
        price_to = params.get("price_to")
        if price_from and price_from.isdigit():
            queryset = queryset.filter(price_rub__gte=int(price_from))
        if price_to and price_to.isdigit():
            queryset = queryset.filter(price_rub__lte=int(price_to))

        color = (params.get("color") or "").strip()
        if color:
            # Prefer indexed color field; keep specs fallback for legacy rows.
            queryset = queryset.filter(
                Q(color__iexact=color) | Q(specs__color__iexact=color)
            )

        transmission = (params.get("transmission") or "").strip()
        if transmission:
            queryset = queryset.filter(
                Q(transmission__icontains=transmission)
                | Q(specs__transmission__icontains=transmission)
                | Q(specs__gearbox__icontains=transmission)
            )

        q = (params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(brand__name__icontains=q)
                | Q(model__icontains=q)
                | Q(description__icontains=q)
            )

        return queryset.order_by("-is_featured", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(nav_context())
        context["available_colors"] = available_colors()

        cat_slug = self.category_slug()
        brand_slug = self.brand_slug()
        context["active_category"] = cat_slug or ""
        context["active_brand"] = brand_slug or ""
        context["current_filters"] = self.request.GET

        get_params = self.request.GET.copy()
        get_params.pop("page", None)
        context["query_string"] = get_params.urlencode()

        path_has_category = bool(self.kwargs.get("category_slug"))
        path_has_brand = bool(self.kwargs.get("brand_slug"))
        thin_listing = has_extra_listing_filters(
            self.request.GET,
            path_has_category=path_has_category,
            path_has_brand=path_has_brand,
        )
        if thin_listing:
            context["meta_robots"] = "noindex, follow"

        context["is_cars_catalog"] = False
        context["is_trucks_catalog"] = False
        context["is_special_catalog"] = False

        category = None
        if cat_slug:
            category = (
                Category.objects.filter(slug=cat_slug).select_related("parent").first()
            )
            if category:
                root = category.parent or category
                context["is_cars_catalog"] = root.slug == "cars"
                context["is_trucks_catalog"] = root.slug == "trucks"
                context["is_special_catalog"] = root.slug == "special"

        context["catalog_root_slug"] = "cars"
        context["listing_brands"] = list(context.get("car_brands") or [])
        context["type_chips"] = [
            {"slug": "cars", "label": "Все легковые"},
            {"slug": "cars_new", "label": "Новые"},
            {"slug": "cars_bought", "label": "Выкупленные"},
        ]
        if context["is_trucks_catalog"]:
            context["catalog_root_slug"] = "trucks"
            context["listing_brands"] = list(context.get("truck_brands") or [])
            context["type_chips"] = [{"slug": "trucks", "label": "Весь коммерческий"}]
            context["type_chips"].extend(
                {"slug": cat.slug, "label": cat.name}
                for cat in (context.get("truck_type_categories") or [])
            )
        elif context["is_special_catalog"]:
            context["catalog_root_slug"] = "special"
            context["listing_brands"] = list(context.get("special_brands") or [])
            context["type_chips"] = [{"slug": "special", "label": "Вся спецтехника"}]
            context["type_chips"].extend(
                {"slug": cat.slug, "label": cat.name}
                for cat in (context.get("special_type_categories") or [])
            )
        elif context["is_cars_catalog"]:
            context["listing_brands"] = list(context.get("car_brands") or [])

        if cat_slug:
            h1, intro = category_heading(
                cat_slug, fallback_name=category.name if category else cat_slug
            )
            if brand_slug:
                brand = Brand.objects.filter(slug=brand_slug).first()
                brand_name = brand.name if brand else brand_slug
                h1 = f"{brand_name}: {h1}"
                intro = (
                    f"Подборка {brand_name} в разделе «{category.name if category else cat_slug}». "
                    + intro
                )
            context["seo_h1"] = h1
            context["seo_intro"] = intro
            context["seo_title"] = f"{h1} | Техника Года"
            context["seo_description"] = intro
        elif brand_slug:
            brand = Brand.objects.filter(slug=brand_slug).first()
            brand_name = brand.name if brand else brand_slug
            h1, intro = brand_heading(brand_name)
            context["seo_h1"] = h1
            context["seo_intro"] = intro
            context["seo_title"] = f"{h1} | Техника Года"
            context["seo_description"] = intro
        else:
            context["seo_h1"] = "Автомобили под заказ из Китая"
            context["seo_intro"] = (
                "Автомобили под заказ из Китая: легковые, коммерческий транспорт и спецтехника. "
                "Подбор под задачу, проверка до оплаты и расчёт под ключ до выдачи в Благовещенске."
            )
            context["seo_title"] = "Автомобили под заказ из Китая | Техника Года"
            context["seo_description"] = context["seo_intro"]

        # Prefer clean canonical for indexable single-dimension routes.
        if not thin_listing:
            if cat_slug and not brand_slug:
                context["canonical_url"] = absolute_url(
                    reverse("catalog:category", kwargs={"category_slug": cat_slug})
                )
            elif brand_slug and not cat_slug:
                context["canonical_url"] = absolute_url(
                    reverse("catalog:brand", kwargs={"brand_slug": brand_slug})
                )
        elif cat_slug and not brand_slug:
            # Filtered/paginated variants canonicalize to the clean category URL.
            context["canonical_url"] = absolute_url(
                reverse("catalog:category", kwargs={"category_slug": cat_slug})
            )
        elif brand_slug and not cat_slug:
            context["canonical_url"] = absolute_url(
                reverse("catalog:brand", kwargs={"brand_slug": brand_slug})
            )

        return context


@ratelimit(key="ip", rate="60/m", method="GET", block=False)
def search_ajax(request):
    """Быстрый поиск для шапки."""
    if getattr(request, "limited", False):
        return JsonResponse([], safe=False, status=429)

    q = request.GET.get("q", "").strip()
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)

    results = Vehicle.objects.filter(
        Q(brand__name__icontains=q) | Q(model__icontains=q) | Q(title__icontains=q),
        is_published=True,
    ).select_related("brand")[:5]

    data = []
    for v in results:
        if v.price_rub is not None:
            price = f"{int(v.price_rub):,} ₽".replace(",", " ")
        else:
            price = "Цена по запросу"
        data.append(
            {
                "title": f"{v.brand.name} {v.model or v.title}",
                "price": price,
                "image": variant_url(v.main_image, 400) if v.main_image else "",
                "url": v.get_absolute_url(),
            }
        )
    return JsonResponse(data, safe=False)


class VehicleDetailView(DetailView):
    model = Vehicle
    template_name = "catalog/detail.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        return (
            Vehicle.objects.filter(is_published=True)
            .select_related("brand", "category", "report")
            .prefetch_related("gallery")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        title = (self.object.title or "").strip()
        title = re.sub(
            r"\s*\([^)]*\b\d{4}\b[^)]*\)\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s+\b\d{4}\b\s*$", "", title)
        display_title = title.strip() or self.object.title
        context["display_title"] = display_title

        description = strip_tags(self.object.description or "") or self.object.title
        words = description.split()
        if len(words) > 30:
            description = " ".join(words[:30]) + "…"

        is_used = bool(
            (self.object.mileage and self.object.mileage > 0)
            or (
                self.object.category
                and self.object.category.slug
                and (
                    "used" in self.object.category.slug
                    or "bought" in self.object.category.slug
                )
            )
        )
        product = {
            "@context": "https://schema.org/",
            "@type": ["Product", "Car"],
            "name": display_title,
            "description": description,
            "sku": self.object.slug,
            "brand": {
                "@type": "Brand",
                "name": self.object.brand.name if self.object.brand_id else "",
            },
            "offers": {
                "@type": "Offer",
                "url": absolute_url(self.object.get_absolute_url()),
                "priceCurrency": "RUB",
                "availability": "https://schema.org/InStock",
                "itemCondition": (
                    "https://schema.org/UsedCondition"
                    if is_used
                    else "https://schema.org/NewCondition"
                ),
            },
        }
        if self.object.model:
            product["model"] = self.object.model
        if self.object.year:
            product["vehicleModelDate"] = str(self.object.year)
        if self.object.mileage is not None:
            product["mileageFromOdometer"] = {
                "@type": "QuantitativeValue",
                "value": int(self.object.mileage),
                "unitCode": "KMT",
            }
        if self.object.color:
            product["color"] = self.object.color
        if self.object.transmission:
            product["vehicleTransmission"] = self.object.transmission
        if self.object.body_type:
            product["bodyType"] = self.object.body_type
        if self.object.horsepower:
            product["vehicleEngine"] = {
                "@type": "EngineSpecification",
                "enginePower": {
                    "@type": "QuantitativeValue",
                    "value": int(self.object.horsepower),
                    "unitCode": "BHP",
                },
            }
        if self.object.main_image:
            product["image"] = absolute_url(self.object.main_image.url)
        if self.object.price_rub is not None:
            product["offers"]["price"] = f"{self.object.price_rub:.0f}"

        crumb_items = [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Главная",
                "item": absolute_url("/"),
            }
        ]
        breadcrumb_links = [{"name": "Главная", "url": reverse("home")}]
        if self.object.category_id:
            cat = self.object.category
            crumb_items.append(
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": cat.name,
                    "item": absolute_url(cat.get_absolute_url()),
                }
            )
            breadcrumb_links.append(
                {"name": cat.name, "url": cat.get_absolute_url()}
            )
            position = 3
        else:
            position = 2
        crumb_items.append(
            {
                "@type": "ListItem",
                "position": position,
                "name": display_title,
                "item": absolute_url(self.object.get_absolute_url()),
            }
        )
        breadcrumb = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": crumb_items,
        }
        context["breadcrumb_links"] = breadcrumb_links
        context["product_json_ld"] = _json_ld(product)
        context["breadcrumb_json_ld"] = _json_ld(breadcrumb)
        context["seo_title"] = f"{display_title} | Техника Года"
        context["seo_description"] = (
            f"{display_title} — в каталоге Техника Года. "
            "Площадка в Китае, проверка до оплаты, цена под ключ до Благовещенска."
        )
        context["canonical_url"] = absolute_url(self.object.get_absolute_url())
        context["og_image_width"] = "1200"
        context["og_image_height"] = "630"
        if self.object.main_image:
            context["og_image_url"] = absolute_url(self.object.main_image.url)
        return context


class VehicleDossierView(DetailView):
    model = Vehicle
    template_name = "catalog/dossier.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        return (
            Vehicle.objects.filter(is_published=True, report__isnull=False)
            .select_related("report")
            .prefetch_related("gallery")
        )


@ratelimit(key="ip", rate="30/m", method="GET", block=True)
def vehicle_report_pdf(request, slug):
    """Serve inspection PDF as attachment (avoids inline XSS via /media/)."""
    vehicle = get_object_or_404(
        Vehicle.objects.filter(is_published=True, report__isnull=False).select_related(
            "report"
        ),
        slug=slug,
    )
    pdf = vehicle.report.pdf_file if vehicle.report_id else None
    if not pdf:
        raise Http404("PDF не найден")
    try:
        handle = pdf.open("rb")
    except Exception as exc:
        raise Http404("PDF не найден") from exc
    response = FileResponse(handle, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="report-{slug}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response

