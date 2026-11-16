"""Ship, aircraft and officer names for the superstate start's five new blocs (superstates_data.py writes the files).

Per bloc: big (BB, BC, CV), medium (CA, CL, CVL) and small (DD, KE, AMC) ship names from member countries'
regions, cities, rivers and historic ships; aircraft makers and names; officer surnames.
"""
POOLS = {
    "India": dict(
        big="Vikrant Viraat Vikramaditya Vishal Delhi Mysore Mumbai Kolkata Chennai Rajput Ranjit Rana Ganga Godavari "
            "Gomati Brahmaputra Betwa Beas Himalaya Vindhya Ashoka Chandragupta Akbar Shivaji".split(),
        medium="Kochi Visakhapatnam Mormugao Imphal Surat Nilgiri Udaygiri Dunagiri Taragiri Vindhyagiri Himgiri "
               "Talwar Trishul Tabar Teg Tarkash Trikand Shivalik Satpura Sahyadri Karachi Dhaka Colombo Lahore "
               "Chittagong Madurai Jaipur Lucknow Hyderabad Cuttack".split(),
        small="Khukri Kuthar Kirpan Khanjar Kora Kirch Kulish Karmuk Kamorta Kadmatt Kiltan Kavaratti Veer Nirbhik "
              "Nipat Nishank Nirghat Vibhuti Vipul Vinash Vidyut Nashak Prahar Prabal Pralaya Abhay Ajay Akshay Agray "
              "Sukanya Subhadra Suvarna Savitri Sharada Sujata Saryu Sunayna Sumedha Sumitra Trinkat Tillanchang "
              "Tarasa Bangaram Bitra Batti Baratang Car Nicobar Chetlat Cora Divh Cheriyam Kalpeni Kabra Koswari "
              "Karuva Magar Gharial Shardul Kesari Airavat".split(),
        makers="Hindustan Aeronautics|Bharat Aerospace|Tata Advanced Systems|Mahindra Aerospace|Taneja Aerospace".split("|"),
        helicopters="Hindustan Aeronautics|Bharat Rotorcraft|Pawan Hans".split("|"),
        aircraft="Tejas Marut Ajeet Kiran Dhruv Rudra Garuda Vayu Baaz Shamsher Vajra Trishul Chetak Cheetah".split(),
        officers="Prakash Mehta Bhagwat Singh Kumar Sharma Nair Menon Pillai Rao Reddy Iyer Verma Joshi Chopra Kapoor "
                 "Dhowan Lanba Suresh Katari Chatterji Nanda Kohli Cursetji Pereira Dawson Tahiliani Nadkarni "
                 "Ramdas Shekhawat Bhushan Gupta Bose Khan Fernando Perera Rahman Chowdhury Hussain Malik".split()),
    "Southeast Asian Union": dict(
        big=["Nusantara", "Majapahit", "Srivijaya", "Angkor", "Ayutthaya", "Sukhothai", "Malacca", "Luzon", "Mindanao",
             "Borneo", "Sumatra", "Java", "Sulawesi", "Mekong", "Irrawaddy", "Chao Phraya", "Rajah Humabon", "Hang Tuah",
             "Gajah Mada", "Naresuan", "Tran Hung Dao", "Bonifacio", "Rizal", "Diponegoro", "Lapu-Lapu"],
        medium=["Jakarta", "Manila", "Bangkok", "Hanoi", "Singapore", "Kuala Lumpur", "Rangoon", "Phnom Penh", "Vientiane",
                "Surabaya", "Cebu", "Davao", "Saigon", "Haiphong", "Da Nang", "Penang", "Johor", "Medan", "Makassar",
                "Palembang", "Bandung", "Chiang Mai", "Mandalay", "Brunei", "Kuching", "Zamboanga", "Semarang", "Hue",
                "Songkhla", "Batam"],
        small=["Lekiu", "Jebat", "Kasturi", "Lekir", "Kedah", "Pahang", "Perak", "Terengganu", "Kelantan", "Selangor",
               "Formidable", "Intrepid", "Steadfast", "Tenacious", "Stalwart", "Supreme", "Victory", "Valour", "Vigilance",
               "Valiant", "Vigour", "Vengeance", "Fatahillah", "Malahayati", "Nala", "Sultan Hasanuddin", "Frans Kaisiepo",
               "Bung Tomo", "Usman Harun", "Martadinata", "Pattimura", "Cut Nyak Dien", "Teuku Umar", "Imam Bonjol",
               "Rattanakosin", "Sukhothai", "Naresuan", "Taksin", "Chakri", "Phutthayotfa", "Kraburi", "Saiburi",
               "Bangpakong", "Pattani", "Narathiwat", "Dinh Tien Hoang", "Ly Thai To", "Quang Trung", "Tran Quoc Toan",
               "Gregorio del Pilar", "Ramon Alcaraz", "Andres Bonifacio", "Emilio Jacinto", "Apolinario Mabini",
               "Artemio Ricarte", "Miguel Malvar", "Magat Salamat", "Aung Zeya", "Kyansittha", "Sin Phyu Shin", "Tabinshwehti",
               "Darussalam", "Darulehsan", "Darulaman"],
        makers=["Indonesian Aerospace", "ST Aerospace", "Thai Aviation Industries", "Aero Bravo Nusantara", "Philippine Aerospace"],
        helicopters=["Indonesian Aerospace", "ST Rotorcraft", "Malaysian Helicopter Works"],
        aircraft=["Garuda", "Rajawali", "Elang", "Naga", "Harimau", "Kris", "Merpati", "Cendrawasih", "Hanuman", "Phraya",
                  "Agila", "Lawin", "Petir", "Halilintar"],
        officers=["Sondakh", "Soebijanto", "Sumardjono", "Purnomo", "Widodo", "Santoso", "Wibowo", "Hidayat", "Anwar", "Ramlan",
                  "Aziz", "Rahman", "Ibrahim", "Hassan", "Lim", "Tan", "Lee", "Ng", "Teo", "Goh", "Santos", "Reyes", "Cruz",
                  "Bautista", "Mercado", "Mayuga", "Nguyen", "Tran", "Le", "Pham", "Hoang", "Do", "Chaiyanam", "Kamthorn",
                  "Sathiraphan", "Thisarak", "Aung", "Thein", "Soe", "Sok"]),
    "United African States": dict(
        big=["Africa", "Uhuru", "Ubuntu", "Kilimanjaro", "Sahara", "Kalahari", "Zambezi", "Limpopo", "Congo", "Niger", "Nile",
             "Table Bay", "Good Hope", "Songhai", "Mali", "Ghana", "Zimbabwe", "Aksum", "Benin", "Mandela", "Nkrumah",
             "Nyerere", "Kenyatta", "Lumumba", "Shaka"],
        medium=["Lagos", "Durban", "Mombasa", "Dakar", "Luanda", "Accra", "Abidjan", "Maputo", "Cape Town", "Port Elizabeth",
                "Dar es Salaam", "Douala", "Freetown", "Conakry", "Libreville", "Walvis Bay", "Zanzibar", "Massawa", "Djibouti",
                "Port Harcourt", "Calabar", "Beira", "Lobito", "Monrovia", "Lome", "Cotonou", "Tema", "Kisumu", "Pointe-Noire",
                "Toamasina"],
        small=["Amatola", "Isandlwana", "Spioenkop", "Mendi", "Drakensberg", "Protea", "Umkhonto", "Assegaai", "Umzimkulu",
               "Umhloti", "Isaac Dyobha", "Galeshewe", "Makhanda", "Aradu", "Thunder", "Unity", "Centenary", "Okpabana",
               "Prosperity", "Karaduwa", "Sagbama", "Ekpe", "Damisa", "Agu", "Siri", "Ayam", "Ekun", "Nyayo", "Umoja",
               "Jasiri", "Shujaa", "Shupavu", "Harambee", "Mamba", "Madaraka", "Jamhuri", "Fouta", "Njambuur", "Kedougou",
               "Ferlo", "Conejera", "Popenguine", "Podor", "Ngola Kiluange", "Nzinga Mbandi", "Rei Bula Matadi", "Pebane",
               "Inhambane", "Chiloane", "Ngunguru", "Mwitongo", "Msoga", "Bamboutos", "Akwayafe", "Le Ntem", "Sanaga",
               "Dipikar", "Elmina", "Sebo", "Achimota", "Yogaga", "Anzone", "Bonsu", "Stephen Otu", "Garinga"],
        makers=["Denel Aviation", "Atlas Aircraft", "Paramount Aerospace", "Aero Africa", "Dornier Technology Nigeria"],
        helicopters=["Denel Rotorcraft", "Atlas Aircraft", "Paramount Rotary"],
        aircraft=["Cheetah", "Impala", "Rooivalk", "Oryx", "Bosbok", "Kudu", "Mamba", "Simba", "Tai", "Mwewe", "Ndege",
                  "Kifaru", "Chui", "Nyati"],
        officers=["Mudimu", "Hlongwane", "Simpson-Anderson", "Retief", "Trainor", "Mhlana", "Litchfield-Tshabalala", "Dlamini",
                  "Nkosi", "Zulu", "Mokoena", "Adekeye", "Afolayan", "Ibrahim", "Ezeoba", "Jibrin", "Ibas", "Okafor", "Bello",
                  "Kibwana", "Mukala", "Wainaina", "Mwathethe", "Otieno", "Diop", "Ndiaye", "Sarr", "Fall", "Biekro", "Quashie",
                  "Amoama", "Dos Santos", "Neto", "Tembo", "Banda", "Kamara", "Diallo", "Traore", "Mensah", "Abebe"]),
    "Middle East Federation": dict(
        big=["Saladin", "Suleiman", "Cyrus", "Darius", "Harun al-Rashid", "Barbarossa", "Yavuz", "Ramses", "Nasser", "Ataturk",
             "Euphrates", "Tigris", "Nile", "Bosphorus", "Anatolia", "Persia", "Arabia", "Mesopotamia", "Levant", "Hejaz",
             "Al Quds", "Mecca", "Medina", "Khorasan", "Sinai"],
        medium=["Istanbul", "Alexandria", "Tehran", "Baghdad", "Cairo", "Riyadh", "Jeddah", "Izmir", "Basra", "Bandar Abbas",
                "Port Said", "Suez", "Dammam", "Kuwait", "Doha", "Abu Dhabi", "Muscat", "Aden", "Beirut", "Latakia", "Tripoli",
                "Benghazi", "Tunis", "Algiers", "Oran", "Casablanca", "Tangier", "Mersin", "Trabzon", "Bushehr"],
        small=["Gaziantep", "Giresun", "Gemlik", "Gelibolu", "Gokceada", "Gediz", "Gokova", "Goksu", "Barbaros", "Orucreis",
               "Salihreis", "Kemalreis", "Yavuz", "Turgutreis", "Fatih", "Yildirim", "Heybeliada", "Buyukada", "Burgazada",
               "Kinaliada", "Alvand", "Alborz", "Sabalan", "Sahand", "Jamaran", "Damavand", "Bayandor", "Naghdi", "Kaman",
               "Zoubin", "Khadang", "Peykan", "Joshan", "Falakhon", "Shamshir", "Gorz", "Gardouneh", "Khanjar", "Neyzeh",
               "Tabarzin", "Sharm el-Sheikh", "Toushka", "Mubarak", "Taba", "Damyat", "Rasheed", "Suez", "Abu Qir",
               "El Suez", "Al Riyadh", "Makkah", "Al Dammam", "Al Madinah", "Hofouf", "Abha", "Taif", "Badr", "Al Yarmook",
               "Hitteen", "Tabuk", "Al Manama", "Al Muharraq", "Abu Dhabi", "Baynunah", "Al Hesen", "Qahir al-Amwaj",
               "Al Mua'zzar", "Rais Hamidou", "Salah Rais", "Rais Ali"],
        makers=["Turkish Aerospace", "Iran Aircraft Industries", "Arab Organization for Industrialization", "Helwan Aircraft",
                "Federal Aerospace"],
        helicopters=["Turkish Aerospace", "Panha", "Arab British Helicopter"],
        aircraft=["Saeqeh", "Azarakhsh", "Kowsar", "Hurkus", "Hurjet", "Kaan", "Atak", "Shahin", "Saqr", "Uqab", "Simurgh",
                  "Shafaq", "Borhan", "Anka"],
        officers=["Sayyari", "Shamkhani", "Khanzadi", "Tangsiri", "Fadavi", "Ornek", "Atac", "Metin", "Bostanoglu", "Ozbal",
                  "Tatlioglu", "Erkaya", "Mameesh", "Tantawi", "Khalid", "Fahmy", "Mamish", "Al Saud", "Al Ghofaily", "Al Bunyan",
                  "Al Thani", "Al Khalifa", "Al Musharrakh", "Al Raisi", "Haddad", "Khoury", "Nasser", "Hussein", "Karim",
                  "Rahimi", "Mousavi", "Hosseini", "Yilmaz", "Demir", "Kaya", "Ben Ali", "Benmoussa", "Gaid Salah", "Larbi",
                  "Zeroual"]),
    "South American Union": dict(
        big=["Sao Paulo", "Minas Gerais", "Rio de Janeiro", "Veinticinco de Mayo", "Independencia", "Almirante Latorre",
             "Almirante Grau", "Bolivar", "San Martin", "O'Higgins", "Sucre", "Artigas", "Tiradentes", "Amazonas", "Rio de la Plata",
             "Patagonia", "Andes", "Pampa", "Orinoco", "Aconcagua", "Libertad", "Atlantico Sul", "Riachuelo", "Humaita",
             "Tamandare"],
        medium=["Buenos Aires", "Santiago", "Lima", "Caracas", "Bogota", "Montevideo", "Valparaiso", "Callao", "Salvador",
                "Recife", "Fortaleza", "Belem", "Santos", "Bahia Blanca", "Rosario", "Cordoba", "Guayaquil", "Cartagena",
                "Maracaibo", "La Guaira", "Punta Arenas", "Talcahuano", "Antofagasta", "Iquique", "Paita", "Mar del Plata",
                "Ushuaia", "Natal", "Vitoria", "Porto Alegre"],
        small=["Niteroi", "Defensora", "Constituicao", "Liberal", "Independencia", "Uniao", "Greenhalgh", "Rademaker", "Bosisio",
               "Dodsworth", "Inhauma", "Jaceguai", "Julio de Noronha", "Frontin", "Barroso", "Almirante Brown", "La Argentina",
               "Heroina", "Sarandi", "Espora", "Rosales", "Spiro", "Parker", "Robinson", "Gomez Roca", "Drummond", "Guerrico",
               "Granville", "Hercules", "Santisima Trinidad", "Almirante Williams", "Almirante Cochrane", "Almirante Condell",
               "Almirante Lynch", "Almirante Blanco Encalada", "Almirante Riveros", "Capitan Prat", "Almirante Uribe",
               "Aguirre", "Carvajal", "Villavisencio", "Montero", "Mariategui", "Palacios", "Bolognesi", "Quinones",
               "Mariscal Sucre", "Almirante Brion", "General Urdaneta", "General Soublette", "General Salom",
               "Almirante Garcia", "Almirante Padilla", "Caldas", "Antioquia", "Esmeraldas", "Manabi", "Los Rios", "El Oro",
               "Galapagos", "Loja", "Uruguay", "General Artigas", "Comandante Pedro Campbell"],
        makers=["Embraer", "FAdeA", "ENAER", "Aermacchi do Brasil", "Industria Aeronautica del Sur"],
        helicopters=["Helibras", "Cicare", "ENAER"],
        aircraft=["Tucano", "Xavante", "Pampa", "Pucara", "Pillan", "Halcon", "Condor", "Carcara", "Gaviao", "Bandeirante",
                  "Xingu", "Guarani", "Dagger", "Yaguarete"],
        officers=["Carvalho", "Moura Neto", "Leal Ferreira", "Saboia", "Guimaraes", "Fonseca", "Barroso", "Tamandare", "Silva",
                  "Souza", "Oliveira", "Pereira", "Godoy", "Stella", "Anaya", "Massera", "Lombardo", "Molina Pico", "Garcia",
                  "Fernandez", "Gonzalez", "Rodriguez", "Vergara", "Codina", "Merino", "Arancibia", "Martinez Busch", "Prat",
                  "Grau", "Montero", "Giampietri", "Ibarcena", "Aponte", "Maniglia", "Padilla", "Soto", "Rojas", "Castro",
                  "Mendoza", "Torres"]),
    # The Cold War starts' minor powers (coldwar_data.py); India uses the pool above.
    "Indonesia": dict(
        big="Irian Nusantara Majapahit Srivijaya Gajah Mada Hasanuddin Diponegoro Pattimura Imam Bonjol Sultan Agung "
            "Teuku Umar Hang Tuah Sudirman Kartini Merdeka Garuda Borobudur Krakatau".split(),
        medium="Jakarta Surabaya Semarang Bandung Medan Palembang Makassar Padang Banjarmasin Pontianak Manado Ambon "
               "Balikpapan Samarinda Denpasar Kupang Jayapura Yogyakarta Surakarta Malang Bogor Cirebon Banda Aceh "
               "Tarakan".split(),
        small="Siliwangi Singamangaraja Sandjaja Sawunggaling Sultan Iskandar Muda Sultan Badarudin Brawijaya "
              "Diponegoro Gadjah Mada Banteng Radjawali Pattimura Sultan Hasanudin Jos Sudarso Slamet Rijadi Ngurah Rai "
              "Monginsidi Lambung Mangkurat Hiu Tjutjut Tongkol Bubara Lajang Lemadang Krapu Dorang Todak Kakap Barakuda "
              "Pandrong Sura Nuku Fatahillah Malahayati Nala Martadinata Samadikun Karel Satsuit Tubun Mongisidi "
              "Ahmad Yani Yos Sudarso Oswald Siahaan Abdul Halim Perdanakusuma Teluk Bone Teluk Langsa Teluk Bayur "
              "Teluk Amboina Teluk Semangka".split(),
        makers="Nurtanio|Dirgantara|Lipnur|Angkasa Jaya".split("|"), helicopters="Nurtanio|Dirgantara".split("|"),
        aircraft="Sikumbang Belalang Kunang Gelatik Kumbang Garuda Elang Rajawali Camar Bangau".split(),
        officers="Subyakto Martadinata Muljadi Sudomo Subono Walujo Sugito Romly Kasenda Sudibyo Arifin Soekarton "
                 "Nasution Siregar Lubis Hutagalung Pane Wibowo Santoso Hartono Kusuma Prabowo Sutrisno Widodo "
                 "Mangkusubroto Tanoto Suryadi Rahardjo Tjokro Latuharhary Pattiasina Lumentut Rumambi Daeng "
                 "Hasibuan Simatupang".split()),
    "Brazil": dict(
        big=["Minas Gerais", "Sao Paulo", "Rio de Janeiro", "Riachuelo", "Aquidaba", "Tamandare", "Barroso", "Amazonas",
             "Tiradentes", "Almirante Saldanha", "Humaita", "Atlantico", "Bahia", "Pernambuco", "Parana", "Deodoro",
             "Floriano", "Marechal Hermes"],
        medium=["Rio Grande do Sul", "Santa Catarina", "Ceara", "Maranhao", "Para", "Paraiba", "Piaui", "Alagoas", "Sergipe",
                "Espirito Santo", "Goias", "Mato Grosso", "Salvador", "Recife", "Fortaleza", "Belem", "Santos", "Natal",
                "Vitoria", "Porto Alegre", "Manaus", "Curitiba", "Niteroi", "Florianopolis"],
        small=["Marcilio Dias", "Mariz e Barros", "Greenhalgh", "Acre", "Ajuricaba", "Amazonas", "Apa", "Araguaia", "Araguari",
               "Bertioga", "Beberibe", "Bracui", "Bauru", "Baependi", "Benevente", "Babitonga", "Bocaina", "Niteroi",
               "Defensora", "Constituicao", "Liberal", "Independencia", "Uniao", "Inhauma", "Jaceguai", "Julio de Noronha",
               "Frontin", "Rademaker", "Bosisio", "Dodsworth", "Para", "Paraiba", "Parana", "Pernambuco", "Piaui",
               "Santa Catarina", "Maranhao", "Mato Grosso", "Sergipe", "Alagoas", "Rio Grande do Norte", "Espirito Santo",
               "Imperial Marinheiro", "Iguatemi", "Ipiranga", "Mearim", "Purus", "Solimoes", "Angostura", "Bahiana",
               "Forte de Coimbra", "Caboclo"],
        makers=["Embraer", "Neiva", "Aerotec", "Companhia Aeronautica Paulista"], helicopters=["Helibras", "Embraer"],
        aircraft=["Tucano", "Xavante", "Bandeirante", "Xingu", "Brasilia", "Carcara", "Gaviao", "Paulistinha", "Universal",
                  "Regente", "Ipanema", "Uirapuru"],
        officers=["Guillobel", "Matoso Maia", "Fonseca", "Saboia", "Guimaraes", "Barroso", "Tamandare", "Silva", "Souza",
                  "Oliveira", "Pereira", "Carvalho", "Moura", "Leal Ferreira", "Rademaker", "Noronha", "Saldanha da Gama",
                  "Alexandrino", "Protogenes", "Aragao", "Bittencourt", "Karam", "Flores", "Serpa", "Santos", "Costa",
                  "Almeida", "Ribeiro", "Azevedo", "Monteiro", "Cunha", "Barbosa", "Lima", "Araujo", "Rocha", "Nunes"]),
    "Argentina": dict(
        big=["Rivadavia", "Moreno", "Veinticinco de Mayo", "Independencia", "General Belgrano", "Nueve de Julio",
             "General San Martin", "Almirante Brown", "Libertad", "Patagonia", "Pueyrredon", "Garibaldi", "Belgrano",
             "San Martin", "Sarmiento", "Mitre", "Pampa", "Malvinas"],
        medium=["La Argentina", "Buenos Aires", "Rosario", "Cordoba", "Mendoza", "Santa Fe", "Entre Rios", "Corrientes",
                "Tucuman", "Salta", "Jujuy", "San Juan", "San Luis", "La Rioja", "Catamarca", "Misiones", "Bahia Blanca",
                "Mar del Plata", "Ushuaia", "La Plata", "Chubut", "Santa Cruz", "Neuquen", "Rio Negro"],
        small=["Hercules", "Santisima Trinidad", "Heroina", "Sarandi", "Espora", "Rosales", "Spiro", "Parker", "Robinson",
               "Gomez Roca", "Drummond", "Guerrico", "Granville", "Segui", "Bouchard", "Piedra Buena", "Storni", "Py",
               "Almirante Domecq Garcia", "Brown", "Cervantes", "Juan de Garay", "Mendoza", "Tucuman", "Misiones",
               "Santa Cruz", "San Luis", "San Juan", "Entre Rios", "Corrientes", "Azopardo", "Piedrabuena", "Murature",
               "King", "Hercules", "Sarandi", "Santisima Trinidad", "Heroina", "Republica", "Comodoro Py", "Somellera",
               "Sobral", "Irigoyen", "Gurruchaga", "Thompson", "Zapiola", "Chiriguano", "Sanaviron", "Diaguita", "Yamana"],
        makers=["FMA", "FAdeA", "Aero Boero", "Chincul"], helicopters=["Cicare", "FMA"],
        aircraft=["Pucara", "Pampa", "Pulqui", "Calquin", "Guarani", "Huanquero", "Nancu", "Dagger", "Halcon", "Condor",
                  "Yaguarete", "Mentor"],
        officers=["Anadon", "Vago", "Lambruschini", "Anaya", "Massera", "Lombardo", "Molina Pico", "Stella", "Godoy",
                  "Garcia", "Fernandez", "Gonzalez", "Rodriguez", "Lopez", "Martinez", "Perez", "Gomez", "Sanchez",
                  "Romero", "Sosa", "Alvarez", "Torres", "Ruiz", "Ramirez", "Storni", "Segui", "Bouchard", "Brown",
                  "Espora", "Rosales", "Py", "Domecq Garcia", "Irizar", "Sobral", "Rojas", "Varela"]),
    "Iran": dict(
        big="Artemiz Kourosh Daryush Shahanshah Persepolis Damavand Sabalan Alborz Zagros Babr Palang Simorgh Rostam "
            "Sohrab Ferdowsi Khayyam Nader Anoushirvan".split(),
        medium="Tehran Tabriz Isfahan Shiraz Mashhad Ahvaz Abadan Bushehr Khorramshahr Bandar Abbas Kerman Yazd Rasht "
               "Hamadan Qazvin Zanjan Ardabil Kermanshah Chabahar Kharg Kish Qeshm Hormuz Larak".split(),
        small="Saam Zaal Rostam Faramarz Bayandor Naghdi Milanian Kahnamuie Alvand Alborz Sabalan Sahand Babr Palang "
              "Damavand Artemiz Kaman Zoubin Khadang Peykan Joshan Falakhon Shamshir Gorz Gardouneh Khanjar Neyzeh "
              "Tabarzin Shahrokh Simorgh Karkas Hengam Larak Tonb Lavan Farur Sirri Karoon Kharg Bandar Abbas Bushehr "
              "Delvar Sirjan Dayer Dilim Charak Chiroo Souru".split(),
        makers="Iran Aircraft Industries|HESA|Shahbaz Aviation".split("|"), helicopters="Panha|HESA".split("|"),
        aircraft="Shahbaz Simorgh Homa Oghab Tondar Azarakhsh Saeqeh Parastu Dorna Tazarv Shabaviz Shahed".split(),
        officers="Bayandor Rasai Madani Habibollahi Attaie Ramzi Afzali Malekzadegan Shamkhani Sayyari Farhadi Karimi "
                 "Hosseini Rezaei Mohammadi Ahmadi Jafari Moradi Kazemi Rahimi Sadeghi Ebrahimi Heidari Akbari Mousavi "
                 "Hashemi Bagheri Najafi Soltani Daryaei Zand Qajar Bakhtiar Amini Tehrani Shirazi".split()),
}
# Korean and Taiwanese names added to Japan's lists for the East Asian Federation.
EAST_ASIA_EXTRA = dict(
    BB=["Sejong the Great", "Yi Sun-sin", "Gwanggaeto", "Formosa"], BC=["Dokdo", "Marado", "Baengnyeong"],
    CA=["Seoul", "Busan", "Taipei", "Kaohsiung"], CL=["Incheon", "Ulsan", "Daegu", "Keelung", "Tainan", "Taichung"],
    DD=["Chungmugong", "Munmu the Great", "Dae Joyeong", "Wang Geon", "Gang Gam-chan", "Choe Yeong", "Eulji Mundeok",
        "Yang Manchun", "Cheng Kung", "Kang Ding", "Si Ning", "Kun Ming", "Di Hua", "Wu Chang", "Cheng De", "Kee Lung"],
    KE=["Pohang", "Gunsan", "Gyeongju", "Mokpo", "Gimcheon", "Chungju", "Jinju", "Yeosu", "Jin Chiang", "Tan Chiang"],
    CV=["Dokdo", "Baekdu"], CVL=["Marado", "Hallasan"])
EAST_ASIA_OFFICERS = ["Kim", "Lee", "Park", "Choi", "Jung", "Song", "Nam", "Yoon", "An", "Chen", "Lin", "Huang", "Wang", "Miao"]


# Real post-war ships, lead ships of their classes first. The game draws a name from the top of a section more
# often than from further down (it walks the list and takes an unused name with some chance, then the first
# unused one), so these come before a bloc's older names: superstates_data.bloc_names puts them first.
def _names(text): return [n.strip() for n in text.replace("\n", " ").split(",") if n.strip()]


_US = dict(
    BB=_names("Iowa, New Jersey, Missouri, Wisconsin"),
    BC=_names("Alaska, Guam, Hawaii"),
    CV=_names("""Forrestal, Kitty Hawk, Enterprise, Nimitz, Saratoga, Ranger, Independence, Constellation, America,
        John F. Kennedy, Dwight D. Eisenhower, Carl Vinson, Theodore Roosevelt, Abraham Lincoln, George Washington,
        John C. Stennis, Harry S. Truman, Ronald Reagan, George H.W. Bush, Gerald R. Ford, Midway, Coral Sea,
        Franklin D. Roosevelt"""),
    CVL=_names("""Iwo Jima, Tarawa, Wasp, Okinawa, Guadalcanal, Guam, Tripoli, New Orleans, Inchon, Saipan,
        Belleau Wood, Nassau, Peleliu, Essex, Kearsarge, Boxer, Bataan, Bonhomme Richard, Makin Island"""),
    CA=_names("""Des Moines, Long Beach, Albany, Ticonderoga, Salem, Newport News, Chicago, Columbus, Boston, Canberra,
        Yorktown, Vincennes, Valley Forge, Bunker Hill, Mobile Bay, Antietam, Leyte Gulf, San Jacinto, Lake Champlain,
        Philippine Sea, Princeton, Normandy, Monterey, Chancellorsville, Cowpens, Gettysburg, Chosin, Hue City, Shiloh,
        Anzio, Vicksburg, Lake Erie, Cape St. George, Vella Gulf, Port Royal"""),
    CL=_names("""Leahy, Belknap, California, Virginia, Bainbridge, Truxtun, Harry E. Yarnell, Worden, Dale,
        Richmond K. Turner, Gridley, England, Halsey, Reeves, Josephus Daniels, Wainwright, Jouett, Horne, Sterett,
        William H. Standley, Fox, Biddle, South Carolina, Texas, Mississippi, Arkansas, Galveston, Little Rock,
        Oklahoma City, Providence, Springfield, Topeka"""),
    DD=_names("""Forrest Sherman, Charles F. Adams, Farragut, Spruance, Kidd, Arleigh Burke, Zumwalt, Coontz, Mitscher,
        Barry, John Paul Jones, Curtis Wilbur, Stout, John S. McCain, Laboon, Russell, Paul Hamilton, Ramage, Fitzgerald,
        Stethem, Carney, Benfold, Gonzalez, Cole, The Sullivans, Milius, Hopper, Ross, Mahan, Decatur, McFaul,
        Donald Cook, Higgins, O'Kane, Porter, Oscar Austin, Roosevelt, Winston S. Churchill, Michael Monsoor,
        Paul F. Foster, Kinkaid, Hewitt, Elliot, Arthur W. Radford, Peterson, Caron, David R. Ray, Oldendorf, John Young,
        O'Brien, Merrill, Briscoe, Stump, Conolly, Moosbrugger, John Hancock, Nicholson, John Rodgers, Leftwich, Cushing,
        Harry W. Hill, O'Bannon, Thorn, Deyo, Ingersoll, Fife, Fletcher, Hayler, Callaghan, Scott, Chandler"""),
    KE=_names("""Dealey, Bronstein, Garcia, Brooke, Knox, Oliver Hazard Perry, Freedom, McCloy, Bradley, Ramsey, Roark,
        Gray, Hepburn, Connole, Rathburne, Meyerkord, Lang, Patterson, Whipple, Reasoner, Lockwood, Stein,
        Marvin Shields, Francis Hammond, Vreeland, Bagley, Downes, Badger, Blakely, Robert E. Peary, Harold E. Holt,
        Trippe, Fanning, Ouellet, Joseph Hewes, Bowen, Paul, Aylwin, Elmer Montgomery, Cook, McCandless,
        Donald B. Beary, Brewton, Kirk, Barbey, Jesse L. Brown, Ainsworth, Miller, Thomas C. Hart, Capodanno, Pharris,
        Truett, Valdez, Moinester, McInerney, Wadsworth, Duncan, Clark, George Philip, Samuel Eliot Morison, Sides,
        Estocin, Clifton Sprague, John A. Moore, Antrim, Flatley, Fahrion, Lewis B. Puller, Jack Williams, Copeland,
        Gallery, Mahlon S. Tisdale, Boone, Stephen W. Groves, Reid, Stark, John L. Hall, Jarrett, Aubrey Fitch,
        Underwood, Crommelin, Curts, Doyle, Halyburton, McClusky, Klakring, Thach, De Wert, Rentz, Nicholas,
        Vandegrift, Robert G. Bradley, Taylor, Gary, Carr, Hawes, Ford, Elrod, Simpson, Reuben James,
        Samuel B. Roberts, Kauffman, Rodney M. Davis, Ingraham, Fort Worth, Coronado"""))
_EUROPE = dict(
    BB=_names("Vanguard, Jean Bart, Richelieu, King George V, Duke of York, Anson, Howe"),
    CV=_names("""Ark Royal, Clemenceau, Eagle, Foch, Victorious, Hermes, Charles de Gaulle, Queen Elizabeth,
        Prince of Wales, Centaur, Albion, Bulwark, Arromanches, Karel Doorman, Dedalo"""),
    CVL=_names("""Invincible, Giuseppe Garibaldi, Principe de Asturias, Illustrious, Cavour, Juan Carlos I, Ocean,
        Jeanne d'Arc, Mistral, Tonnerre, Dixmude, Vittorio Veneto, Trieste"""),
    CA=_names("Colbert, Tiger, Andrea Doria, De Grasse, Caio Duilio, Lion, Blake, De Zeven Provincien, De Ruyter, Canarias"),
    CL=_names("""Devonshire, Bristol, Suffren, Hampshire, Kent, London, Fife, Glamorgan, Antrim, Norfolk, Duquesne,
        Belfast, Superb, Swiftsure"""),
    DD=_names("""Daring, Sheffield, Georges Leygues, Tourville, Lutjens, Audace, Hamburg, Cassard, Forbin,
        Alvaro de Bazan, Tromp, Sachsen, Birmingham, Coventry, Glasgow, Manchester, Dauntless, Diamond, Dragon,
        Defender, Duncan, Chevalier Paul, Molders, Rommel, Hessen, Ardito, Durand de la Penne, Impavido, Dupleix,
        Montcalm, Jean de Vienne, Primauguet, La Motte-Picquet, Latouche-Treville, Duguay-Trouin, De Grasse, Exeter,
        Southampton, Nottingham, Liverpool, York, Gloucester, Edinburgh, Cardiff, Newcastle, Schleswig-Holstein,
        Bayern, Francesco Mimbelli, Almirante Juan de Borbon, Blas de Lezo, Mendez Nunez, Cristobal Colon"""),
    KE=_names("""Leander, Whitby, Rothesay, Amazon, Broadsword, Bremen, Maestrale, Lupo, Kortenaer, La Fayette,
        D'Estienne d'Orves, Baleares, Descubierta, Santa Maria, Oslo, Brandenburg, Floreal, Karel Doorman, Wielingen,
        Niels Juel, Hydra, Yavuz, Fridtjof Nansen, Aquitaine, Carlo Bergamini, Ashanti, Ajax, Arethusa, Argonaut,
        Andromeda, Battleaxe, Brilliant, Brazen, Boxer, Cornwall, Cumberland, Campbeltown, Chatham, Argyll, Lancaster,
        Marlborough, Iron Duke, Monmouth, Montrose, Westminster, Northumberland, Richmond, Somerset, Sutherland, Kent,
        Portland, St Albans, Koln, Karlsruhe, Emden, Niedersachsen, Rheinland-Pfalz, Augsburg, Lubeck, Surcouf,
        Courbet, Aconit, Guepratte, Libeccio, Grecale, Scirocco, Aliseo, Euro, Espero, Zeffiro, Sagittario, Perseo,
        Orsa, Van Speijk, Van Galen, Van Nes, Van Amstel, Navarra, Victoria, Numancia, Reina Sofia, Canarias"""))
_RUSSIA = dict(
    BC=_names("Kirov, Stalingrad, Frunze, Kalinin, Pyotr Velikiy, Admiral Ushakov, Admiral Lazarev, Admiral Nakhimov, Moskva"),
    CV=_names("Admiral Kuznetsov, Kiev, Ulyanovsk, Varyag, Minsk, Novorossiysk, Baku, Admiral Gorshkov"),
    CVL=_names("Moskva, Leningrad"),
    CA=_names("""Sverdlov, Slava, Dzerzhinsky, Ordzhonikidze, Zhdanov, Marshal Ustinov, Chervona Ukraina, Admiral Lobov,
        Aleksandr Suvorov, Admiral Senyavin, Mikhail Kutuzov, Murmansk, Dmitry Pozharsky, Aleksandr Nevsky"""),
    CL=_names("""Grozny, Admiral Zozulya, Kronshtadt, Nikolayev, Admiral Fokin, Admiral Golovko, Varyag, Vladivostok,
        Vitse-Admiral Drozd, Sevastopol, Admiral Isakov, Admiral Makarov, Marshal Voroshilov, Admiral Oktyabrsky,
        Admiral Isachenkov, Marshal Timoshenko, Vasily Chapayev, Admiral Yumashev, Ochakov, Kerch, Azov,
        Petropavlovsk, Tashkent"""),
    DD=_names("""Skory, Spokoyny, Komsomolets Ukrainy, Sovremenny, Udaloy, Neustrashimy, Bedovy, Gnevny, Otchayanny,
        Otlichny, Osmotritelny, Bezuprechny, Boyevoy, Stoyky, Okrylenny, Burny, Gremyashchy, Bystry, Rastoropny,
        Bezboyaznenny, Bespokoyny, Nastoychivy, Vitse-Admiral Kulakov, Marshal Vasilevsky, Admiral Zakharov,
        Admiral Spiridonov, Admiral Tributs, Marshal Shaposhnikov, Severomorsk, Admiral Levchenko, Admiral Vinogradov,
        Admiral Kharlamov, Admiral Panteleyev, Admiral Chabanenko, Soobrazitelny, Provorny, Obraztsovy, Odarenny,
        Steregushchy, Krasny Kavkaz, Reshitelny, Strogy, Smetlivy, Krasny Krym, Sposobny, Sderzhanny, Svetly, Speshny,
        Skromny, Uporny, Boyky, Derzky, Zorky"""),
    KE=_names("""Bditelny, Gornostay, Bodry, Svirepy, Storozhevoy, Razyashchy, Razumny, Druzhny, Dostoyny, Doblestny,
        Deyatelny, Zharky, Retivy, Leningradsky Komsomolets, Letuchy, Pylky, Zadorny, Bezzavetny, Bezukoriznenny,
        Ladny, Poryvisty, Rezvy, Rezky, Grozyashchy, Neukrotimy, Gromky, Pytlivy, Yaroslav Mudry, Tatarstan, Dagestan,
        Admiral Kasatonov, Admiral Grigorovich, Admiral Essen, Boiky, Stoiky"""))
_CHINA = dict(
    CV=_names("Liaoning, Shandong, Fujian"),
    CVL=_names("Hainan, Guangxi, Anhui"),
    CA=_names("Nanchang, Lhasa, Dalian, Anshan, Wuxi, Yan'an, Zunyi, Xianyang"),
    DD=_names("""Anshan, Jinan, Harbin, Shenzhen, Hangzhou, Guangzhou, Lanzhou, Shenyang, Kunming, Fushun, Changchun,
        Taiyuan, Xi'an, Yinchuan, Xining, Kaifeng, Guilin, Zhanjiang, Zhuhai, Qingdao, Fuzhou, Taizhou, Ningbo, Wuhan,
        Haikou, Zhengzhou, Shijiazhuang, Changsha, Hefei, Xiamen, Urumqi, Guiyang, Nanjing, Hohhot, Chengdu, Qiqihar,
        Zibo, Tangshan, Suzhou, Huainan"""),
    KE=_names("""Chengdu, Xiaguan, Yingtan, Jiujiang, Wuhu, Anqing, Ma'anshan, Xuzhou, Nanchong, Kaiyuan, Changde,
        Shaoxing, Nantong, Huayin, Zhenjiang, Nanping, Ji'an, Changzhi, Jinhua, Dandong, Siping, Huaibei, Tongling,
        Jiangmen, Foshan, Yichang, Yulin, Yuxi, Xiangyang, Huaihua, Luoyang, Mianyang, Wenzhou, Zhoushan, Huangshan,
        Hengyang, Yuncheng, Yantai, Yancheng, Linyi, Yiyang, Changzhou, Weifang, Liuzhou, Sanya, Yueyang, Handan,
        Daqing, Xuchang"""))
_JAPAN = dict(
    CVL=_names("Izumo, Hyuga, Kaga, Ise"),
    DD=_names("""Harukaze, Ayanami, Murasame, Akizuki, Takatsuki, Haruna, Shirane, Tachikaze, Hatsuyuki, Hatakaze,
        Asagiri, Kongo, Takanami, Atago, Asahi, Maya, Yukikaze, Teruzuki, Amatsukaze, Yamagumo, Kikuzuki, Mochizuki,
        Nagatsuki, Minegumo, Hiei, Kurama, Asakaze, Sawakaze, Shirayuki, Mineyuki, Sawayuki, Hamayuki, Isoyuki,
        Haruyuki, Yamayuki, Matsuyuki, Setoyuki, Asayuki, Shimayuki, Shimakaze, Yamagiri, Yugiri, Amagiri, Hamagiri,
        Setogiri, Sawagiri, Umigiri, Kirishima, Myoko, Chokai, Harusame, Yudachi, Kirisame, Inazuma, Samidare,
        Ikazuchi, Akebono, Ariake, Onami, Makinami, Sazanami, Suzunami, Ashigara, Suzutsuki, Fuyuzuki, Shiranui,
        Haguro"""),
    KE=_names("""Akebono, Ikazuchi, Isuzu, Chikugo, Ishikari, Yubari, Abukuma, Mogami, Inazuma, Kitakami, Oi, Ayase,
        Mikuma, Tokachi, Iwase, Chitose, Niyodo, Teshio, Yoshino, Kumano, Noshiro, Yubetsu, Jintsu, Oyodo, Sendai,
        Chikuma, Tone, Yahagi, Agano"""))
HISTORIC = {"United States of America": _US, "United States": _US, "European NATO": _EUROPE, "European Union": _EUROPE,
            "Warsaw Pact": _RUSSIA, "Russian Federation": _RUSSIA, "Communist China": _CHINA,
            "People's Republic of China": _CHINA, "State of Japan": _JAPAN, "East Asian Federation": _JAPAN}
