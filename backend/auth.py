"""
Authentication & Role-Based Access Control (RBAC) Module.
Roles:
- VIEWER: View authorized dashboard metrics and public heatmaps.
- ANALYST: Inspect detailed analytical results, transaction graphs, and metrics.
- AUTHORIZED_OFFICER: Review AI leads, approve tactical alerts, prepare simulated requisition packages.
- ADMIN: Manage configuration, audit logs, and security parameters.
"""

from fastapi import HTTPException, Header, Security, Depends
from typing import Optional, List

ROLES = ["VIEWER", "ANALYST", "AUTHORIZED_OFFICER", "ADMIN"]

def get_current_user_role(x_role: Optional[str] = Header(default="AUTHORIZED_OFFICER")) -> str:
    """Extracts role from HTTP header for demonstration purposes."""
    role = x_role.upper() if x_role else "AUTHORIZED_OFFICER"
    if role not in ROLES:
        raise HTTPException(status_code=403, detail=f"Invalid or unauthorized role: {role}")
    return role

def require_role(allowed_roles: List[str]):
    def role_checker(current_role: str = Depends(get_current_user_role)):
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Access forbidden for role {current_role}. Required one of: {allowed_roles}"
            )
        return current_role
    return role_checker
