import json
import os
import keepassxc_proxy_client
import keepassxc_proxy_client.protocol

class KeePassCred:

    def __init__(self, kp, url, login, password, totp):
        self.kp = kp
        self.url = url
        self.login = login
        self.totp = totp        
        self.password = password
    
    def get_totp(self) -> str:
        return self.kp.get_login(self.url, self.login).totp
    


class KeePass:
    def __init__(self):
        self.setup = False
        self.config_file = '.keepass.json'  # Name of the config file

    def lazy_init(self):
        self.connection = keepassxc_proxy_client.protocol.Connection()
        self.connection.connect()

        # Read keypass config file
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                try:
                    config = json.load(f)
                    name = config.get('association_name')
                    public_key = config.get('association_key')
                    if name and public_key:
                        public_key = bytes.fromhex(public_key)  # Convert hex string to bytes
                        self.connection.load_associate(name, public_key)
                        self.connection.test_associate()
                        self.setup = True
                except json.JSONDecodeError:
                    print(f"Error decoding JSON in {self.config_file}")

        else:  # If no valid config file was found
            self.connection.associate()
            self.setup = True

            association_name = self.connection.dump_associate()[0]
            association_key = self.connection.dump_associate()[1]

            # Save to keypass config file
            with open(self.config_file, 'w') as f:
                json.dump({
                    'association_name': association_name,
                    'association_key': association_key.hex()  # Store as hex string
                }, f, indent=4)
                
                
    def get_logins(self,url):
        self.lazy_init()
        
        # print(self.connection.get_databasehash())
        # # This will open a keepassxc dialogue
        # print(self.connection.test_associate())
        # print(self.connection.dump_associate())
        # print(self.connection.get_logins("https://github.com"))
        
        # print(self.connection.get_logins(url))
        return self.connection.get_logins(url)

    def get_login(self, url, login=None) -> KeePassCred:
        """
        Gets the login credentials for the given URL.

        Args:
          url: The URL to search for.
          login: (Optional) The login/username to filter by. 
                 If not provided, any login for the URL will be returned.

        Returns:
          A KeePassCred object with the login and password.

        Raises:
          ValueError: If no logins are found for the URL, 
                      if multiple logins are found (and no login filter is provided), 
                      or if no matching login is found when a login filter is provided.
        """

        logins = all_logins = self.get_logins(url)

        if not logins:
            raise ValueError(f"No password found for URL: {url}")

        if login:  # If a login filter is provided
            logins = [entry for entry in logins if entry['login'] == login]
            if not logins:
                raise ValueError(f"No password found for URL {url} with login {login} (of {all_logins} logins)")

        if len(logins) > 1:  # If multiple logins are found (and no filter or filter didn't narrow it down)
            raise ValueError(f"Multiple passwords found for URL: {url}\n{logins}")

        return KeePassCred(self, url, logins[0]['login'], logins[0]['password'], logins[0].get('totp'))