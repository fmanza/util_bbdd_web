"""Esquemas HTTP de la API v1. Las contraseñas son solo de entrada (``SecretStr``) y nunca salen en respuestas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_core import PydanticCustomError

from app.domain.identity.passwords import MAX_PASSWORD_LENGTH
from app.domain.identity.permissions import Permission

ColorScheme = Literal["light", "dark", "auto"]
Language = Literal["es", "en"]
BuiltinRole = Literal["admin", "user"]
Username = Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
DisplayName = Annotated[str, Field(min_length=1, max_length=128)]
Password = Annotated[SecretStr, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]

MAX_PAGE_SIZE = 200


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------------------------------------------


class CsrfToken(BaseModel):
    """Token CSRF para la cabecera ``X-CSRF-Token``."""

    csrf_token: str


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""

    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Password


class PasswordChange(BaseModel):
    """Cambio de la propia contraseña."""

    current_password: Password
    new_password: Password


class RoleRef(_Out):
    """Rol de un usuario (ADR-014)."""

    id: int
    name: str
    builtin: BuiltinRole | None = Field(description="``admin`` o ``user`` en los roles base; null en los demás")


class Me(_Out):
    """Usuario de la sesión actual."""

    id: int
    username: str
    display_name: str
    role: RoleRef
    permissions: list[Permission] = Field(description="Permisos de su rol (ADR-014)")
    color_scheme: ColorScheme = Field(description="Tema de la interfaz: claro, oscuro o el del sistema (``auto``)")
    language: Language = Field(description="Idioma de la interfaz")


class PreferencesUpdate(BaseModel):
    """Preferencias de la propia cuenta: al menos una; un campo desconocido da 422."""

    model_config = ConfigDict(extra="forbid")

    color_scheme: ColorScheme | None = Field(
        default=None, description="Tema de la interfaz: claro, oscuro o el del sistema (``auto``)"
    )
    language: Language | None = Field(default=None, description="Idioma de la interfaz")

    @model_validator(mode="after")
    def _at_least_one(self) -> PreferencesUpdate:
        if self.color_scheme is None and self.language is None:
            raise PydanticCustomError("api.preferences_empty", "api.preferences_empty")
        return self


# --- users ------------------------------------------------------------------------------------------------------


class UserOut(_Out):
    """Usuario visto por un administrador."""

    id: int
    username: str
    display_name: str
    role: RoleRef
    permissions: list[Permission] = Field(description="Permisos de su rol")
    is_active: bool
    storage_quota_mb: int | None = Field(
        default=None, description="Cuota propia en MB (0 = sin límite); null = la global (ADR-012)"
    )
    locked_until: datetime | None
    password_changed_at: datetime
    created_at: datetime
    updated_at: datetime
    project_count: int = Field(default=0, description="Proyectos de los que es miembro")


class UserCreate(BaseModel):
    """Alta de usuario con las mismas opciones que la edición (salvo la contraseña, que es obligatoria)."""

    username: Username
    display_name: DisplayName
    password: Password
    role_id: int | None = Field(default=None, description="Rol (ADR-014); sin él, el rol base «Usuario»")
    is_active: bool = True
    storage_quota_mb: Annotated[int | None, Field(ge=0, le=10_000_000)] = Field(
        default=None, description="Cuota propia en MB (0 = sin límite); null = la global (ADR-012)"
    )


class UserUpdate(BaseModel):
    """Edición parcial de usuario; ``password`` restablece la contraseña y cierra sus sesiones."""

    display_name: DisplayName | None = None
    role_id: int | None = Field(default=None, description="Rol nuevo (ADR-014); cierra sus sesiones")
    is_active: bool | None = None
    storage_quota_mb: Annotated[int | None, Field(ge=0, le=10_000_000)] = Field(
        default=None, description="Cuota propia en MB (0 = sin límite); ``null`` explícito vuelve a la global"
    )
    password: Password | None = None

    @property
    def global_storage_quota(self) -> bool:
        """Se envió ``storage_quota_mb: null``: quitar la cuota propia."""
        return "storage_quota_mb" in self.model_fields_set and self.storage_quota_mb is None


# --- roles ------------------------------------------------------------------------------------------------------

RoleName = Annotated[str, Field(min_length=1, max_length=64)]


class PermissionOut(BaseModel):
    """Permiso del catálogo (ADR-014)."""

    name: Permission
    group: Literal["admin", "databases"] = Field(description="Administración o capacidades sobre bases de datos")


class RoleOut(_Out):
    """Rol con sus permisos efectivos y su número de usuarios."""

    id: int
    name: str
    builtin: BuiltinRole | None = Field(description="``admin`` o ``user`` en los roles base (no se borran)")
    permissions: list[Permission]
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    """Alta de un rol personalizado."""

    name: RoleName
    permissions: list[str] = Field(default_factory=list, max_length=64)


class RoleUpdate(BaseModel):
    """Cambio de nombre o de permisos (los roles base no cambian)."""

    name: RoleName | None = None
    permissions: list[str] | None = Field(default=None, max_length=64)


class UserPage(BaseModel):
    """Página de usuarios."""

    items: list[UserOut]
    total: int
    active_admins: int = Field(description="Administradores activos en total (no solo los de la página)")


class BlockingProject(BaseModel):
    """Proyecto que impide borrar un usuario; ``role`` es su rol de miembro (null si solo lo creó)."""

    id: int
    name: str
    role: Literal["owner", "editor", "viewer"] | None = None


class BlockingConnection(BaseModel):
    """Conexión que impide borrar un usuario: compartida o asociada a algún proyecto."""

    id: int
    name: str
    visibility: Literal["private", "shared"]


class UserDeletionCheck(BaseModel):
    """Si se puede borrar un usuario y, si no, por qué (``reasons``: ``self``, ``last_admin``, ``member``,
    ``creator``, ``connections``)."""

    can_delete: bool
    reasons: list[Literal["self", "last_admin", "member", "creator", "connections"]]
    projects: list[BlockingProject] = Field(description="Proyectos de los que es miembro")
    created_projects: list[BlockingProject] = Field(
        description="Proyectos que creó: su carpeta del workspace cuelga de la suya"
    )
    connections: list[BlockingConnection]


class TransferItem(BaseModel):
    """Proyecto o conexión afectados por una transferencia; ``new_name`` si choca con uno del destino."""

    id: int
    name: str
    new_name: str | None = None
    role: Literal["owner", "editor", "viewer"] | None = None
    visibility: Literal["private", "shared"] | None = None


class UserTransferRequest(BaseModel):
    """Transferir a ``target_user_id`` lo que impide borrar al usuario."""

    target_user_id: int
    remove_memberships: bool = Field(
        default=False, description="Quitar además al usuario de todos los proyectos (tras ceder la propiedad)"
    )


class UserTransfer(BaseModel):
    """Vista previa o resultado de una transferencia (``reasons``: ``same_user``, ``target_inactive``,
    ``target_cannot_share``, ``busy``)."""

    can_transfer: bool
    reasons: list[Literal["same_user", "target_inactive", "target_cannot_share", "busy"]]
    created_projects: list[TransferItem] = Field(description="Proyectos que creó: cambian de carpeta")
    owned_projects: list[TransferItem] = Field(description="Proyectos de los que es propietario: el destino también")
    other_memberships: list[TransferItem] = Field(
        description="Proyectos donde es editor o lector (se quitan con remove_memberships)"
    )
    connections: list[TransferItem] = Field(description="Conexiones compartidas o asociadas a proyectos")
    busy_projects: list[TransferItem] = Field(description="Proyectos creados con ejecuciones en cola o en curso")


# --- sessions ---------------------------------------------------------------------------------------------------


class SessionOut(_Out):
    """Sesión activa; nunca incluye el token."""

    id: int
    user_id: int
    username: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class SessionPage(BaseModel):
    """Página de sesiones."""

    items: list[SessionOut]
    total: int


# --- audit ------------------------------------------------------------------------------------------------------


class AuditEntryOut(_Out):
    """Evento de auditoría."""

    id: int
    ts: datetime
    actor_user_id: int | None
    actor_username: str | None
    action: str
    outcome: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    details: dict[str, object] | None


class AuditPage(BaseModel):
    """Página de auditoría."""

    items: list[AuditEntryOut]
    total: int


# --- engines ----------------------------------------------------------------------------------------------------


class DriverOut(_Out):
    """Driver del motor y si está instalado en el servidor."""

    name: str
    installed: bool


class CapabilitiesOut(_Out):
    """Matriz de capacidades del motor (``get_engine_capabilities`` de util_bbdd 4.6.0)."""

    async_supported: bool
    migrate_source: bool
    migrate_target: bool
    readiness: bool
    documentation: bool = Field(description="Documentación (DatabaseDocumentation)")
    graphs: bool = Field(description="Grafos de relaciones")
    compare: bool = Field(description="Comparación de esquemas (SchemaComparator)")
    dump: bool = Field(description="Volcado de datos, como origen o destino")
    dump_constraints: bool = Field(description="El volcado desactiva y reactiva las constraints del destino")
    bulk: bool = Field(description="Carga bulk desde fichero (BulkCrud)")


class ParamOut(_Out):
    """Parámetro de conexión del motor; ``kind`` indica cómo lo trata la aplicación."""

    name: str
    type: Literal["string", "integer", "float", "boolean", "object"]
    required: bool
    default: Any = None
    options: list[str] | None
    description: str
    kind: Literal["plain", "secret", "host", "port", "path", "blocked"]


class EngineOut(_Out):
    """Motor del catálogo."""

    db_type: str
    name: str
    description: str
    version_range: str
    default_port: int | None
    drivers: list[DriverOut]
    capabilities: CapabilitiesOut


class EngineDetailOut(EngineOut):
    """Ficha completa de un motor."""

    url_docs: str | None
    features: list[str]
    driver_package: str | None
    install_command: str | None
    system_requirements: list[str]
    params: list[ParamOut]


# --- connections ------------------------------------------------------------------------------------------------

ConnectionName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=500)]
ConnectionPassword = Annotated[SecretStr, Field(min_length=1, max_length=512)]
Visibility = Literal["private", "shared"]


class ConnectionCreate(BaseModel):
    """Alta de conexión. ``password`` solo se escribe: se cifra y nunca se devuelve."""

    name: ConnectionName
    db_type: Annotated[str, Field(min_length=1, max_length=32)]
    description: Description = ""
    params: dict[str, Any] = Field(default_factory=dict)
    password: ConnectionPassword | None = None
    read_only: bool = True
    visibility: Visibility = "private"


class ConnectionUpdate(BaseModel):
    """Edición parcial. ``params`` sustituye a todos los parámetros; sin ``password`` se conserva la guardada."""

    name: ConnectionName | None = None
    description: Description | None = None
    params: dict[str, Any] | None = None
    password: ConnectionPassword | None = None
    read_only: bool | None = None
    visibility: Visibility | None = None


class ConnectionOut(BaseModel):
    """Conexión sin secretos; ``has_password`` indica si hay contraseña guardada."""

    id: int
    name: str
    db_type: str
    description: str
    params: dict[str, Any]
    has_password: bool
    read_only: bool
    visibility: Visibility
    owner_id: int
    owner_username: str
    editable: bool
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime


class ConnectionPage(BaseModel):
    """Página de conexiones."""

    items: list[ConnectionOut]
    total: int


class ProbeErrorOut(BaseModel):
    """Error saneado de una prueba: código estable y mensaje para el usuario (nunca el texto del driver)."""

    code: str
    message: str


class ConnectionTestOut(BaseModel):
    """Resultado de una prueba de conexión."""

    ok: bool
    duration_ms: int
    server_version: str | None
    tested_at: datetime
    error: ProbeErrorOut | None


class ReadinessFindingOut(BaseModel):
    """Hallazgo de readiness."""

    level: str
    param: str
    current: str
    recommendation: str


class ReadinessOut(BaseModel):
    """Informe de readiness; ``detail`` explica por qué no hubo checks dinámicos (solo el tipo de error)."""

    supported: bool
    dynamic: bool
    detail: str | None
    checked_at: datetime | None
    findings: list[ReadinessFindingOut]
    error: ProbeErrorOut | None


# --- allowlist --------------------------------------------------------------------------------------------------


class AllowlistEntryIn(BaseModel):
    """Destino permitido: red CIDR, IP, nombre de host o comodín ``*.dominio``."""

    pattern: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str, Field(max_length=255)] = ""


class AllowlistEntryOut(_Out):
    """Destino permitido."""

    id: int
    pattern: str
    description: str
    created_at: datetime
