from sharepoint_utils import (
    download_file_from_onedrive,
    extract_excel_row,
    check_file_exists_on_sharepoint,
    create_word_from_template,
    upload_file_to_sharepoint,
    create_temp_directory,
    clean_directory,
    convert_word_to_pdf
)
from pathlib import Path
import pandas as pd
import logging
from datetime import datetime
import schedule
import time
import os

# Configuration de l'intervalle (en minutes)
interval_minutes = int(os.environ.get('INTERVAL_MINUTES', 60))  # Configurable via variable d'environnement
# Configuration pour activer/désactiver la conversion PDF
convert_to_pdf_enabled = False

# Configuration - Utiliser SharePoint pour le fichier Excel
remote_sharepoint_name = "sharepoint"
remote_exel_file_path = "diagnostic_maturite.xlsx"
local_tmp_dir = "temp"
remote_word_folder = "Diagnostics"
remote_word_model = "modele_diagnostic_maturite.docx"

# Configurer le logger
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

def main():

    print("--------------------------")
    print("Remote folder: ", remote_word_folder)
    # Créer le répertoire temporaire local s'il n'existe pas
    local_dir = Path(local_tmp_dir)
    local_dir.mkdir(exist_ok=True)

    # Supression des fichiers temporaires
    clean_directory(local_dir)
    
    # 1. Télécharger le fichier Excel depuis SharePoint
    logger.info(f"Téléchargement du fichier Excel {remote_exel_file_path}...")
    excel_file = download_file_from_onedrive(remote_sharepoint_name, remote_exel_file_path, local_dir)
    
    if not excel_file:
        logger.error("Impossible de télécharger le fichier Excel. Arrêt du traitement.")
        return False
    
    # 2. Télécharger le modèle Word depuis SharePoint (à chaque fois)
    logger.info(f"Téléchargement du modèle Word {remote_word_model} depuis SharePoint...")
    local_model_path = download_file_from_onedrive(remote_sharepoint_name, remote_word_model, local_dir)
    
    if not local_model_path:
        logger.error("Impossible de télécharger le modèle Word. Arrêt du traitement.")
        return False
    
    # 3. Lire toutes les lignes du fichier Excel
    try:
        df = pd.read_excel(excel_file, dtype=str)  # Tout lire comme texte pour éviter les problèmes de format
        
        if df.empty:
            logger.warning("Le fichier Excel ne contient aucune donnée.")
            return False
            
        # 4. Traiter chaque ligne du fichier Excel
        for index, row in df.iterrows():
            # Nettoyer les données: remplacer NaN par chaîne vide
            row = row.fillna('')
            
            # Générer un nom de fichier basé sur une colonne de l'Excel ou utiliser un identifiant unique
            if 'Organisme' in row and row['Organisme']:
                safe_name = row['Organisme'].replace(' ', '_').lower()
                word_filename = f"diagnostic_{safe_name}.docx"
            else:
                logger.info(f"Ligne {index} ignorée : colonne 'Organisme' manquante ou vide.")
                continue
            
            # Vérifier si le fichier existe déjà sur SharePoint
            if check_file_exists_on_sharepoint(remote_sharepoint_name, remote_word_folder, word_filename):
                logger.info(f"Le fichier {word_filename} existe déjà sur SharePoint. Traitement ignoré.")
                continue
            
            # Créer le document Word à partir du modèle et des données de la ligne
            output_path = local_dir / word_filename
            result_path = create_word_from_template(local_model_path, row, output_path)
            
            if not result_path:
                logger.error(f"Échec de création du document Word pour la ligne {index}.")
                continue
                
            # Upload du fichier Word généré vers SharePoint
            logger.info(f"Téléversement du fichier Word {word_filename} vers SharePoint...")
            upload_success = upload_file_to_sharepoint(result_path, remote_sharepoint_name, remote_word_folder)
            
            if upload_success:
                logger.info(f"Fichier Word {word_filename} téléversé avec succès.")
            else:
                logger.error(f"Échec du téléversement du fichier Word {word_filename}.")
            
            # Conversion du fichier Word en PDF seulement si activé
            if convert_to_pdf_enabled:
                pdf_path = convert_word_to_pdf(result_path)
                
                if pdf_path:
                    # Upload du fichier PDF généré vers SharePoint
                    pdf_filename = pdf_path.name
                    logger.info(f"Téléversement du fichier PDF {pdf_filename} vers SharePoint...")
                    pdf_upload_success = upload_file_to_sharepoint(pdf_path, remote_sharepoint_name, remote_word_folder)
                    
                    if pdf_upload_success:
                        logger.info(f"Fichier PDF {pdf_filename} téléversé avec succès.")
                    else:
                        logger.error(f"Échec du téléversement du fichier PDF {pdf_filename}.")
                else:
                    logger.error(f"Échec de conversion en PDF pour la ligne {index}.")
            else:
                logger.info(f"Conversion en PDF désactivée pour {word_filename}.")
                
        logger.info("Traitement terminé avec succès.")
        return True
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement du fichier Excel: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Traitement automatique des diagnostics ===")
    
    # Exécuter une fois immédiatement
    success = main()
    print("Terminé" if success else "Erreur lors du traitement")
    
    # Configurer l'exécution périodique
    print(f"Configuration de l'exécution automatique toutes les {interval_minutes} minutes...")
    schedule.every(interval_minutes).minutes.do(main)
    
    # Boucle pour maintenir le scheduler en exécution
    print("Le scheduler est actif. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du scheduler.")