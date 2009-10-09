from cms.admin.change_list import ReplaceChangeListAdmin, get_changelist_admin
from reversion.admin import VersionAdmin as RealVersionAdmin

VersionAdmin = get_changelist_admin(RealVersionAdmin)