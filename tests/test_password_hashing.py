
from auth.security import hash_password, verify_password

def test_password_hashing():

    password = "TestPassword123!"

    # Generate password hash
    hashed_password = hash_password(password)

    # Hash should not equal original password
    assert hashed_password != password

    # Correct password should verify
    assert verify_password(password, hashed_password) is True

    # Incorrect password should fail
    assert verify_password("WrongPassword", hashed_password) is False

    # Same password should produce different hashes
    another_hash = hash_password(password)

    assert another_hash != hashed_password

    # Both hashes should verify against the same password
    assert verify_password(password, another_hash) is True

    print("All password hashing tests passed!")

if __name__ == "__main__":
    test_password_hashing()