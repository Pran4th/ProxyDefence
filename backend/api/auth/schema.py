from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    organization: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class NotificationPreferencesRequest(BaseModel):
    critical_threat_alerts: bool = True
    weekly_reports: bool = True
    simulation_results: bool = False
    system_updates: bool = True


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
