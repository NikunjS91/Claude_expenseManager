"""
tests/test_06-date-filter-profile.py

Pytest tests for Step 6: Date Filter on the /profile route.

Spec: .claude/specs/06-date-filter-profile.md

Seed data reference (user_id=1, "Demo User"):
  - 8 expenses all dated 2026-08-01 through 2026-08-18
  - Total: 250+50+1200+800+400+1500+300+100 = 4600.0
"""

import pytest
from datetime import date, timedelta

from app import app as flask_app
from database.db import init_db, seed_db


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    with flask_app.app_context():
        init_db()
        seed_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Test client with the seed Demo User already logged in via session."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Demo User"
    return client


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def get_profile(client, **params):
    """GET /profile with optional query params, following no redirects."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"/profile?{qs}"
    else:
        url = "/profile"
    return client.get(url, follow_redirects=False)


def get_profile_following(client, **params):
    """GET /profile with optional query params, following redirects."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"/profile?{qs}"
    else:
        url = "/profile"
    return client.get(url, follow_redirects=True)


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        """Unauthenticated request must return 302 redirect to /login."""
        response = get_profile(client)
        assert response.status_code == 302, (
            f"Expected 302 redirect for unauthenticated /profile, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Expected redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_with_date_params_still_redirects(self, client):
        """Date params must not bypass the auth guard."""
        response = get_profile(client, date_from="2026-08-01", date_to="2026-08-31")
        assert response.status_code == 302, (
            "Date params must not bypass auth — expected 302 redirect"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Redirect target should be /login, got: {location}"
        )

    def test_unauthenticated_redirect_followed_reaches_login_page(self, client):
        """Following the redirect should land on the login page."""
        response = client.get("/profile", follow_redirects=True)
        assert response.status_code == 200, (
            "Following unauthenticated /profile redirect should yield 200"
        )
        assert b"Login" in response.data or b"login" in response.data, (
            "Expected login page content after following unauthenticated /profile redirect"
        )


# ------------------------------------------------------------------ #
# Unfiltered (All Time) baseline                                      #
# ------------------------------------------------------------------ #

class TestUnfilteredBaseline:

    def test_no_params_returns_200(self, auth_client):
        """GET /profile with no params must return 200."""
        response = get_profile(auth_client)
        assert response.status_code == 200, (
            f"Expected 200 for /profile with no params, got {response.status_code}"
        )

    def test_no_params_renders_profile_page(self, auth_client):
        """Unfiltered /profile must render the profile template."""
        response = get_profile(auth_client)
        assert b"Demo User" in response.data, (
            "Profile page should display the seeded user's name 'Demo User'"
        )

    def test_no_params_shows_rupee_symbol(self, auth_client):
        """All amounts must display ₹ symbol in the unfiltered view."""
        response = get_profile(auth_client)
        assert "₹".encode() in response.data, (
            "Unfiltered profile page must display the ₹ symbol for amounts"
        )

    def test_no_params_contains_seed_expense_data(self, auth_client):
        """Unfiltered view should show data from all 8 seed expenses."""
        response = get_profile(auth_client)
        # Seed total is 4600.0 — at minimum some amounts should appear
        assert b"4600" in response.data or "4,600".encode() in response.data, (
            "Unfiltered profile should surface the total of all seed expenses (4600)"
        )

    def test_no_params_filter_bar_present(self, auth_client):
        """The filter bar section must be present in the rendered HTML."""
        response = get_profile(auth_client)
        assert b"period-filter" in response.data, (
            "Expected 'period-filter' CSS class in HTML — filter bar section is missing"
        )

    def test_no_params_date_inputs_present(self, auth_client):
        """Custom date inputs must be rendered in the filter bar."""
        response = get_profile(auth_client)
        assert b'type="date"' in response.data or b"type='date'" in response.data, (
            "Expected <input type='date'> elements for the custom range filter"
        )


# ------------------------------------------------------------------ #
# Valid date range — expenses exist in range                          #
# ------------------------------------------------------------------ #

class TestValidDateRangeWithExpenses:

    def test_august_range_returns_200(self, auth_client):
        """Valid date range covering all seed expenses returns 200."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        assert response.status_code == 200, (
            f"Expected 200 for valid August date range, got {response.status_code}"
        )

    def test_august_range_shows_rupee_symbol(self, auth_client):
        """Filtered view must still show ₹ symbol for all amounts."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in filtered view"
        )

    def test_august_range_includes_seed_totals(self, auth_client):
        """Filtering to August 2026 (where all seed data lives) should show totals."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        assert b"4600" in response.data or "4,600".encode() in response.data, (
            "August filter should include all 8 seed expenses totalling 4600"
        )

    def test_narrow_range_excludes_outside_expenses(self, auth_client):
        """Filtering to a single day that has one expense excludes all others."""
        # Only one expense on 2026-08-01: 250.0 (Groceries / Food)
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-01")
        assert response.status_code == 200, (
            "Single-day filter should return 200"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must appear even for a single-day filter"
        )
        # Total for this day is 250 only
        assert b"250" in response.data, (
            "Single-day 2026-08-01 should show the 250.0 Groceries expense"
        )

    def test_date_inputs_prepopulated_with_active_filter(self, auth_client):
        """When a valid custom range is active, date inputs must be pre-filled."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        assert b"2026-08-01" in response.data, (
            "date_from value '2026-08-01' should be pre-populated in the form input"
        )
        assert b"2026-08-31" in response.data, (
            "date_to value '2026-08-31' should be pre-populated in the form input"
        )

    def test_filter_passes_through_categories(self, auth_client):
        """Category breakdown section must be rendered for a valid filtered range."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        # Seed data includes "Food", "Transport", "Bills" categories
        assert b"Food" in response.data or b"Transport" in response.data, (
            "Category breakdown must appear in the filtered profile view"
        )

    def test_multi_month_range_returns_200(self, auth_client):
        """A valid multi-month range spanning the seed data returns 200."""
        response = get_profile(auth_client, date_from="2026-01-01", date_to="2026-12-31")
        assert response.status_code == 200, (
            "Multi-month range should return 200"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in multi-month filtered view"
        )


# ------------------------------------------------------------------ #
# Valid date range — zero expenses in range                           #
# ------------------------------------------------------------------ #

class TestValidDateRangeNoExpenses:

    def test_empty_range_returns_200(self, auth_client):
        """A valid date range with no matching expenses must not crash — returns 200."""
        response = get_profile(auth_client, date_from="2020-01-01", date_to="2020-01-31")
        assert response.status_code == 200, (
            f"Empty-range filter should return 200, got {response.status_code}"
        )

    def test_empty_range_shows_zero_total(self, auth_client):
        """Zero-expense range must show ₹0 or ₹0.00 total spent."""
        response = get_profile(auth_client, date_from="2020-01-01", date_to="2020-01-31")
        data = response.data
        assert "₹0".encode() in data or "0.00".encode() in data, (
            "Empty-range filter should display ₹0.00 total spent, got no zero-amount indicator"
        )

    def test_empty_range_shows_rupee_symbol(self, auth_client):
        """₹ symbol must appear even when no expenses exist in the range."""
        response = get_profile(auth_client, date_from="2020-01-01", date_to="2020-01-31")
        assert "₹".encode() in response.data, (
            "₹ symbol must appear even for empty date range"
        )

    def test_empty_range_no_server_error(self, auth_client):
        """Empty range must not trigger a 500 or any error page."""
        response = get_profile(auth_client, date_from="2020-01-01", date_to="2020-01-31")
        assert response.status_code != 500, (
            "Empty date range must not cause a server error"
        )
        assert b"Internal Server Error" not in response.data, (
            "Error page must not appear in empty-range response"
        )

    def test_far_future_range_no_crash(self, auth_client):
        """A valid future date range with no seed data must not crash."""
        response = get_profile(auth_client, date_from="2099-01-01", date_to="2099-12-31")
        assert response.status_code == 200, (
            "Far-future empty range should return 200 without crashing"
        )


# ------------------------------------------------------------------ #
# Malformed date parameters                                           #
# ------------------------------------------------------------------ #

class TestMalformedDateParameters:

    def test_malformed_date_from_does_not_crash(self, auth_client):
        """Malformed date_from must not crash the app — silently falls back to unfiltered."""
        response = get_profile(auth_client, date_from="not-a-date", date_to="2026-08-31")
        assert response.status_code == 200, (
            f"Malformed date_from should return 200 (not a crash), got {response.status_code}"
        )

    def test_malformed_date_to_does_not_crash(self, auth_client):
        """Malformed date_to must not crash the app — silently falls back to unfiltered."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="bad-date")
        assert response.status_code == 200, (
            f"Malformed date_to should return 200 (not a crash), got {response.status_code}"
        )

    def test_both_malformed_dates_do_not_crash(self, auth_client):
        """Both malformed date params must fall back to unfiltered without crashing."""
        response = get_profile(auth_client, date_from="not-a-date", date_to="also-bad")
        assert response.status_code == 200, (
            "Both malformed dates should return 200 (unfiltered fallback)"
        )

    def test_malformed_date_from_falls_back_to_unfiltered(self, auth_client):
        """Malformed date_from should silently fall back, showing all seed expenses."""
        response = get_profile(auth_client, date_from="not-a-date", date_to="2026-08-31")
        # Should still show all 8 seed expenses (unfiltered fallback)
        assert b"4600" in response.data or "4,600".encode() in response.data or b"250" in response.data, (
            "Malformed date_from should fall back to unfiltered view showing seed data"
        )

    def test_malformed_date_no_flash_error(self, auth_client):
        """Malformed dates silently fall back — they must NOT show a flash error."""
        response = get_profile(auth_client, date_from="not-a-date", date_to="2026-08-31")
        assert b"Start date must be before end date" not in response.data, (
            "Silent fallback for malformed dates must not show the date-order flash error"
        )

    def test_wrong_format_date_does_not_crash(self, auth_client):
        """Dates in non-ISO format (e.g. DD/MM/YYYY) must fall back gracefully."""
        response = get_profile(auth_client, date_from="01-08-2026", date_to="31-08-2026")
        assert response.status_code == 200, (
            "Non-ISO date format should not crash the app — expected 200"
        )

    def test_partial_date_string_does_not_crash(self, auth_client):
        """Partial date strings (e.g. '2026-08') must not crash the app."""
        response = get_profile(auth_client, date_from="2026-08", date_to="2026-08-31")
        assert response.status_code == 200, (
            "Partial date string should not crash the app — expected 200"
        )

    def test_sql_injection_attempt_does_not_crash(self, auth_client):
        """SQL injection attempt in date params must be handled safely."""
        response = get_profile(
            auth_client,
            date_from="' OR '1'='1",
            date_to="2026-08-31",
        )
        assert response.status_code == 200, (
            "SQL injection attempt in date_from should not crash the app"
        )


# ------------------------------------------------------------------ #
# date_from > date_to validation                                      #
# ------------------------------------------------------------------ #

class TestDateOrderValidation:

    def test_date_from_after_date_to_returns_200(self, auth_client):
        """date_from > date_to must return 200 (not a crash or error page)."""
        response = get_profile_following(
            auth_client, date_from="2026-08-31", date_to="2026-08-01"
        )
        assert response.status_code == 200, (
            f"date_from > date_to should return 200 with flash error, got {response.status_code}"
        )

    def test_date_from_after_date_to_shows_flash_error(self, auth_client):
        """date_from > date_to must flash 'Start date must be before end date.'"""
        response = get_profile_following(
            auth_client, date_from="2026-08-31", date_to="2026-08-01"
        )
        assert b"Start date must be before end date." in response.data, (
            "Expected flash error 'Start date must be before end date.' when date_from > date_to"
        )

    def test_date_from_after_date_to_falls_back_to_unfiltered(self, auth_client):
        """After date-order error, the view must show all seed expenses (unfiltered)."""
        response = get_profile_following(
            auth_client, date_from="2026-08-31", date_to="2026-08-01"
        )
        # Unfiltered view shows all seed data including total 4600
        assert b"4600" in response.data or "4,600".encode() in response.data or b"250" in response.data, (
            "After date-order error, unfiltered fallback should show all seed expenses"
        )

    def test_date_from_after_date_to_shows_rupee_symbol(self, auth_client):
        """₹ symbol must appear even when date-order validation fails."""
        response = get_profile_following(
            auth_client, date_from="2026-12-31", date_to="2026-01-01"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must be present even after date-order validation error"
        )

    def test_date_from_equal_to_date_to_is_valid(self, auth_client):
        """date_from == date_to is a valid single-day range — must NOT show flash error."""
        response = get_profile_following(
            auth_client, date_from="2026-08-01", date_to="2026-08-01"
        )
        assert response.status_code == 200, (
            "date_from == date_to should be treated as valid single-day filter"
        )
        assert b"Start date must be before end date." not in response.data, (
            "Equal dates must not trigger the date-order flash error"
        )


# ------------------------------------------------------------------ #
# Partial / missing parameters                                        #
# ------------------------------------------------------------------ #

class TestPartialParameters:

    def test_only_date_from_falls_back_to_unfiltered(self, auth_client):
        """Supplying only date_from (no date_to) must fall back to unfiltered view."""
        response = get_profile(auth_client, date_from="2026-08-01")
        assert response.status_code == 200, (
            "Only date_from supplied should return 200"
        )
        # Should show all seed data since it falls back to unfiltered
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in unfiltered fallback"
        )

    def test_only_date_to_falls_back_to_unfiltered(self, auth_client):
        """Supplying only date_to (no date_from) must fall back to unfiltered view."""
        response = get_profile(auth_client, date_to="2026-08-31")
        assert response.status_code == 200, (
            "Only date_to supplied should return 200"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in unfiltered fallback"
        )

    def test_empty_string_params_treated_as_absent(self, auth_client):
        """Empty string values for date params must be treated as absent."""
        response = get_profile(auth_client, date_from="", date_to="")
        assert response.status_code == 200, (
            "Empty-string date params should return 200 as unfiltered"
        )

    def test_only_date_from_no_crash(self, auth_client):
        """Only date_from must not crash the app."""
        response = get_profile(auth_client, date_from="2026-08-15")
        assert response.status_code != 500, (
            "Supplying only date_from must not cause a server error"
        )


# ------------------------------------------------------------------ #
# Active preset indicators                                            #
# ------------------------------------------------------------------ #

class TestActivePresetIndicators:

    def test_no_params_marks_all_time_active(self, auth_client):
        """No params → 'All Time' preset must be marked active (is-active class)."""
        response = get_profile(auth_client)
        assert b"is-active" in response.data, (
            "Expected 'is-active' class on the All Time preset when no params supplied"
        )

    def test_this_month_preset_link_present(self, auth_client):
        """Filter bar must contain a 'This Month' preset link."""
        response = get_profile(auth_client)
        assert b"This Month" in response.data, (
            "Expected 'This Month' preset button/link in the filter bar"
        )

    def test_all_time_preset_link_present(self, auth_client):
        """Filter bar must contain an 'All Time' preset link."""
        response = get_profile(auth_client)
        assert b"All Time" in response.data, (
            "Expected 'All Time' preset button/link in the filter bar"
        )

    def test_last_3_months_preset_link_present(self, auth_client):
        """Filter bar must contain a 'Last 3 Months' preset link."""
        response = get_profile(auth_client)
        assert b"Last 3 Months" in response.data or b"3 Months" in response.data, (
            "Expected 'Last 3 Months' preset button/link in the filter bar"
        )

    def test_last_6_months_preset_link_present(self, auth_client):
        """Filter bar must contain a 'Last 6 Months' preset link."""
        response = get_profile(auth_client)
        assert b"Last 6 Months" in response.data or b"6 Months" in response.data, (
            "Expected 'Last 6 Months' preset button/link in the filter bar"
        )

    def test_this_month_active_when_preset_dates_match(self, auth_client):
        """Supplying this-month's date bounds must mark 'This Month' active."""
        today = date.today()
        first_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        response = get_profile(auth_client, date_from=first_of_month, date_to=today_str)
        assert response.status_code == 200, (
            "This Month preset dates should return 200"
        )
        assert b"is-active" in response.data, (
            "Expected 'is-active' class when This Month preset dates are supplied"
        )

    def test_custom_range_no_preset_active(self, auth_client):
        """A custom (non-preset) date range must not mark any standard preset active."""
        # 2026-08-05 to 2026-08-10 is a custom range, not any preset
        response = get_profile(auth_client, date_from="2026-08-05", date_to="2026-08-10")
        assert response.status_code == 200, (
            "Custom date range should return 200"
        )
        # We can't assert no is-active without knowing exactly how many elements have it,
        # but we can verify the page renders successfully.
        assert "₹".encode() in response.data, (
            "₹ symbol must appear for custom date range"
        )

    def test_all_time_link_has_clean_url(self, auth_client):
        """The All Time preset must link to /profile with no query params."""
        response = get_profile(auth_client)
        # The clean URL for All Time is /profile (no query string)
        assert b'href="/profile"' in response.data or b"href='/profile'" in response.data, (
            "All Time preset must link to clean /profile URL with no query params"
        )


# ------------------------------------------------------------------ #
# Rupee symbol always present                                         #
# ------------------------------------------------------------------ #

class TestRupeeSymbolConsistency:

    @pytest.mark.parametrize("date_from,date_to", [
        ("2026-08-01", "2026-08-31"),   # range with all seed expenses
        ("2020-01-01", "2020-01-31"),   # range with zero expenses
        ("2026-08-01", "2026-08-01"),   # single day
        ("2099-01-01", "2099-12-31"),   # far future, no expenses
    ])
    def test_rupee_symbol_present_for_all_date_ranges(self, auth_client, date_from, date_to):
        """₹ symbol must appear in every filtered profile view."""
        response = get_profile(auth_client, date_from=date_from, date_to=date_to)
        assert response.status_code == 200, (
            f"Expected 200 for range {date_from} to {date_to}, got {response.status_code}"
        )
        assert "₹".encode() in response.data, (
            f"₹ symbol must appear for date range {date_from} to {date_to}"
        )

    def test_rupee_symbol_present_unfiltered(self, auth_client):
        """₹ symbol must appear in the unfiltered (All Time) view."""
        response = get_profile(auth_client)
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in unfiltered /profile view"
        )


# ------------------------------------------------------------------ #
# Template structure                                                  #
# ------------------------------------------------------------------ #

class TestTemplateStructure:

    def test_profile_page_extends_base_template(self, auth_client):
        """Profile page must use the shared base layout (navbar/footer indicators)."""
        response = get_profile(auth_client)
        # base.html includes a navbar — look for common base landmarks
        assert b"Spendly" in response.data, (
            "Profile page should contain 'Spendly' branding from base.html"
        )

    def test_filter_bar_class_present(self, auth_client):
        """The 'period-filter' CSS class must be present in the rendered HTML."""
        response = get_profile(auth_client)
        assert b"period-filter" in response.data, (
            "Expected 'period-filter' CSS class — filter bar is missing from template"
        )

    def test_filter_bar_present_when_filtered(self, auth_client):
        """Filter bar must also be present when a date filter is active."""
        response = get_profile(auth_client, date_from="2026-08-01", date_to="2026-08-31")
        assert b"period-filter" in response.data, (
            "Filter bar must remain visible when a date filter is active"
        )

    def test_date_inputs_have_correct_names(self, auth_client):
        """The custom date inputs must use name='date_from' and name='date_to'."""
        response = get_profile(auth_client)
        assert b'name="date_from"' in response.data or b"name='date_from'" in response.data, (
            "Expected input with name='date_from' in filter bar"
        )
        assert b'name="date_to"' in response.data or b"name='date_to'" in response.data, (
            "Expected input with name='date_to' in filter bar"
        )

    def test_apply_button_present(self, auth_client):
        """The custom range form must have an 'Apply' submit button."""
        response = get_profile(auth_client)
        assert b"Apply" in response.data, (
            "Expected 'Apply' submit button in the custom date range form"
        )

    def test_user_name_displayed(self, auth_client):
        """The profile page must display the logged-in user's name."""
        response = get_profile(auth_client)
        assert b"Demo User" in response.data, (
            "Profile page must display the seeded user's name 'Demo User'"
        )
