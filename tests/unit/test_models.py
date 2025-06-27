from notion_dev.core.models import AsanaTask, Feature


class TestAsanaTask:
    """Test AsanaTask model functionality"""
    
    def test_extract_feature_code_from_title(self):
        """Test extracting feature code from task title"""
        task = AsanaTask(
            gid="123456789",
            name="CC01 - Implement authentication",
            notes="",
            assignee_gid="user123",
            completed=False
        )
        
        code = task.extract_feature_code()
        assert code == "CC01"
        assert task.feature_code == "CC01"
        assert task.feature_codes == ["CC01"]
    
    def test_extract_multiple_feature_codes(self):
        """Test extracting multiple feature codes"""
        task = AsanaTask(
            gid="123456789",
            name="AU01 DA02 - Integration of auth and dashboard",
            notes="",
            assignee_gid="user123",
            completed=False
        )
        
        code = task.extract_feature_code()
        assert code == "AU01"  # First code is primary
        assert task.feature_codes == ["AU01", "DA02"]
    
    def test_extract_feature_code_from_notes(self):
        """Test extracting feature code from notes when not in title"""
        task = AsanaTask(
            gid="123456789",
            name="Implement new feature",
            notes="Feature Code: API03",
            assignee_gid="user123",
            completed=False
        )
        
        code = task.extract_feature_code()
        assert code == "API03"
        assert task.feature_code == "API03"
    
    def test_no_feature_code(self):
        """Test when no feature code is present"""
        task = AsanaTask(
            gid="123456789",
            name="Random task without code",
            notes="No code here",
            assignee_gid="user123",
            completed=False
        )
        
        code = task.extract_feature_code()
        assert code is None
        assert task.feature_code is None
        assert task.feature_codes == []


class TestFeature:
    """Test Feature model functionality"""
    
    def test_feature_is_active(self):
        """Test feature active status"""
        feature = Feature(
            code="CC01",
            name="User Access",
            status="validated",
            module_name="Auth Module",
            plan=["premium"],
            user_rights=["admin"],
            notion_id="12345",
            content="Feature content"
        )
        
        assert feature.is_active is True
        
        feature.status = "draft"
        assert feature.is_active is False
    
    def test_feature_full_context(self):
        """Test feature context generation"""
        feature = Feature(
            code="CC01",
            name="User Access",
            status="validated",
            module_name="Auth Module",
            plan=["premium", "enterprise"],
            user_rights=["admin", "user"],
            notion_id="12345",
            content="Feature content here"
        )
        
        context = feature.get_full_context()
        assert "CC01" in context
        assert "User Access" in context
        assert "premium, enterprise" in context
        assert "admin, user" in context